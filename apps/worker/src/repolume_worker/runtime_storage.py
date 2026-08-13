"""Direct worker persistence operations against the shared analysis schema."""

import re
from dataclasses import dataclass

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from repolume_worker.architecture_models import RepositoryArchitectureArtifact
from repolume_worker.jobs import JobStatus

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
_FAILURE_CODE = re.compile(r"[a-z][a-z0-9_]{0,99}", re.ASCII)
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"cloning", "failed"}),
    "cloning": frozenset({"analyzing", "failed"}),
    "analyzing": frozenset({"completed", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
}

metadata = MetaData()
analysis_jobs = Table(
    "analysis_jobs",
    metadata,
    Column("analysis_id", String(64), primary_key=True),
    Column("provider", String(32), nullable=False),
    Column("owner", String(39), nullable=False),
    Column("repository", String(100), nullable=False),
    Column("canonical_url", String(2048), nullable=False),
    Column("requested_ref", String(255)),
    Column("commit_sha", String(40)),
    Column("status", String(16), nullable=False),
    Column("failure_code", String(100)),
    Column("failure_message", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    Column("version", Integer, nullable=False, server_default="1"),
)
analysis_architectures = Table(
    "analysis_architectures",
    metadata,
    Column(
        "analysis_id",
        String(64),
        ForeignKey("analysis_jobs.analysis_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("schema_version", String(32), nullable=False),
    Column("payload", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


class WorkerStorageError(RuntimeError):
    """Base error for worker persistence operations."""


class WorkerJobNotFound(WorkerStorageError):
    """Raised when a queue message references no durable job."""


class WorkerStorageConflict(WorkerStorageError):
    """Raised when another delivery already changed the expected job state."""


@dataclass(frozen=True, slots=True)
class WorkerJobState:
    analysis_id: str
    status: JobStatus
    commit_sha: str | None


class WorkerAnalysisStorage:
    """Persist worker lifecycle changes with compare-and-set updates."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    @staticmethod
    def _validate_commit_sha(commit_sha: str) -> None:
        if not _COMMIT_SHA.fullmatch(commit_sha):
            raise ValueError("commit_sha must be a lowercase 40-character hexadecimal SHA")

    def get_job(self, analysis_id: str) -> WorkerJobState:
        with self._sessions() as session:
            row = session.execute(
                select(
                    analysis_jobs.c.analysis_id,
                    analysis_jobs.c.status,
                    analysis_jobs.c.commit_sha,
                ).where(analysis_jobs.c.analysis_id == analysis_id)
            ).one_or_none()
        if row is None:
            raise WorkerJobNotFound("The analysis job does not exist.")
        try:
            status = JobStatus(row.status)
        except ValueError as exc:
            raise WorkerStorageError("The analysis job has an invalid status.") from exc
        return WorkerJobState(row.analysis_id, status, row.commit_sha)

    def transition(
        self,
        analysis_id: str,
        *,
        expected_status: JobStatus,
        next_status: JobStatus,
        commit_sha: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> WorkerJobState:
        if next_status.value not in _ALLOWED_TRANSITIONS[expected_status.value]:
            raise ValueError("invalid worker analysis transition")
        if next_status is JobStatus.COMPLETED:
            raise ValueError("use complete to store the architecture atomically")
        if commit_sha is not None:
            self._validate_commit_sha(commit_sha)
        is_failure = next_status is JobStatus.FAILED
        if is_failure != (failure_code is not None and failure_message is not None):
            raise ValueError("failed transitions require both safe failure fields")
        if is_failure and (
            not _FAILURE_CODE.fullmatch(failure_code or "")
            or not failure_message
            or failure_message != failure_message.strip()
            or len(failure_message) > 500
        ):
            raise ValueError("failure fields must be safe, non-empty, and bounded")

        values: dict[str, object] = {
            "status": next_status.value,
            "failure_code": failure_code,
            "failure_message": failure_message,
            "updated_at": func.now(),
            "finished_at": func.now() if is_failure else None,
            "version": analysis_jobs.c.version + 1,
        }
        if commit_sha is not None:
            values["commit_sha"] = commit_sha
        with self._sessions.begin() as session:
            result = session.execute(
                update(analysis_jobs)
                .where(
                    analysis_jobs.c.analysis_id == analysis_id,
                    analysis_jobs.c.status == expected_status.value,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                self._raise_miss(session, analysis_id)
        return self.get_job(analysis_id)

    def complete(
        self,
        analysis_id: str,
        *,
        commit_sha: str,
        architecture: RepositoryArchitectureArtifact,
    ) -> WorkerJobState:
        self._validate_commit_sha(commit_sha)
        if architecture.schema_version != "1.0":
            raise ValueError("architecture schema version is not supported")
        try:
            with self._sessions.begin() as session:
                result = session.execute(
                    update(analysis_jobs)
                    .where(
                        analysis_jobs.c.analysis_id == analysis_id,
                        analysis_jobs.c.status == JobStatus.ANALYZING.value,
                    )
                    .values(
                        status=JobStatus.COMPLETED.value,
                        commit_sha=commit_sha,
                        failure_code=None,
                        failure_message=None,
                        updated_at=func.now(),
                        finished_at=func.now(),
                        version=analysis_jobs.c.version + 1,
                    )
                )
                if result.rowcount != 1:
                    self._raise_miss(session, analysis_id)
                session.execute(
                    insert(analysis_architectures).values(
                        analysis_id=analysis_id,
                        schema_version=architecture.schema_version,
                        payload=architecture.to_dict(),
                    )
                )
        except IntegrityError as exc:
            raise WorkerStorageConflict("The analysis result was already stored.") from exc
        return self.get_job(analysis_id)

    @staticmethod
    def _raise_miss(session, analysis_id: str) -> None:
        exists = session.scalar(
            select(analysis_jobs.c.analysis_id).where(analysis_jobs.c.analysis_id == analysis_id)
        )
        if exists is None:
            raise WorkerJobNotFound("The analysis job does not exist.")
        raise WorkerStorageConflict("The analysis job state changed before this update.")
