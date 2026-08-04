"""Transactional storage operations for analysis jobs and architecture results."""

import re
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import Engine, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from repolume_api.analysis_schemas import AnalysisStatus, RepositoryArchitectureResponse
from repolume_api.database_models import AnalysisArchitectureModel, AnalysisJobModel
from repolume_api.repositories import RepositoryReference

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
_FAILURE_CODE = re.compile(r"[a-z][a-z0-9_]{0,99}", re.ASCII)
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"cloning", "failed"}),
    "cloning": frozenset({"analyzing", "failed"}),
    "analyzing": frozenset({"completed", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
}


class AnalysisStorageError(RuntimeError):
    """Base class for controlled storage failures."""


class AnalysisAlreadyExists(AnalysisStorageError):
    """Raised when an analysis identifier is reused."""


class StoredAnalysisNotFound(AnalysisStorageError):
    """Raised when an analysis identifier is absent."""


class StoredAnalysisNotCompleted(AnalysisStorageError):
    """Raised when architecture is requested for a non-completed job."""


class AnalysisTransitionConflict(AnalysisStorageError):
    """Raised when compare-and-set lifecycle state no longer matches."""


class AnalysisStorageCorrupt(AnalysisStorageError):
    """Raised when stored state violates the application contract."""


@dataclass(frozen=True, slots=True)
class StoredAnalysisJob:
    """Storage-neutral snapshot of a durable analysis job."""

    analysis_id: str
    status: AnalysisStatus
    repository: RepositoryReference
    commit_sha: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    version: int


class AnalysisStorage:
    """Persist jobs through short transactions and guarded lifecycle updates."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    @staticmethod
    def _snapshot(model: AnalysisJobModel) -> StoredAnalysisJob:
        return StoredAnalysisJob(
            analysis_id=model.analysis_id,
            status=model.status,  # type: ignore[arg-type]
            repository=RepositoryReference(
                owner=model.owner,
                repository=model.repository,
                ref=model.requested_ref,
            ),
            commit_sha=model.commit_sha,
            failure_code=model.failure_code,
            failure_message=model.failure_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            finished_at=model.finished_at,
            version=model.version,
        )

    @staticmethod
    def _validate_analysis_id(analysis_id: str) -> None:
        if (
            not analysis_id
            or len(analysis_id) > 64
            or not re.fullmatch(r"[A-Za-z0-9_-]+", analysis_id)
        ):
            raise ValueError("analysis_id must contain 1 to 64 safe characters")

    @staticmethod
    def _validate_commit_sha(commit_sha: str) -> None:
        if not _COMMIT_SHA.fullmatch(commit_sha):
            raise ValueError("commit_sha must be a lowercase 40-character hexadecimal SHA")

    @staticmethod
    def _get_model(session: Session, analysis_id: str) -> AnalysisJobModel:
        model = session.get(AnalysisJobModel, analysis_id)
        if model is None:
            raise StoredAnalysisNotFound("The analysis does not exist.")
        return model

    def create_job(
        self,
        analysis_id: str,
        repository: RepositoryReference,
    ) -> StoredAnalysisJob:
        """Create one queued job without publishing it to a worker."""

        self._validate_analysis_id(analysis_id)
        model = AnalysisJobModel(
            analysis_id=analysis_id,
            provider="github",
            owner=repository.owner,
            repository=repository.repository,
            canonical_url=repository.canonical_url,
            requested_ref=repository.ref,
            status="queued",
        )
        try:
            with self._sessions.begin() as session:
                session.add(model)
                session.flush()
                session.refresh(model)
        except IntegrityError as exc:
            raise AnalysisAlreadyExists("The analysis identifier already exists.") from exc
        return self._snapshot(model)

    def get_job(self, analysis_id: str) -> StoredAnalysisJob:
        """Read one job snapshot in a short-lived session."""

        self._validate_analysis_id(analysis_id)
        with self._sessions() as session:
            return self._snapshot(self._get_model(session, analysis_id))

    def transition_job(
        self,
        analysis_id: str,
        *,
        expected_status: AnalysisStatus,
        next_status: AnalysisStatus,
        commit_sha: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> StoredAnalysisJob:
        """Advance state only when the persisted status matches the caller's view."""

        self._validate_analysis_id(analysis_id)
        if expected_status not in _ALLOWED_TRANSITIONS or next_status not in _ALLOWED_TRANSITIONS:
            raise ValueError("unknown analysis status")
        if next_status == "completed":
            raise ValueError("use complete_job to persist completion and architecture atomically")
        if next_status not in _ALLOWED_TRANSITIONS[expected_status]:
            raise ValueError(f"invalid analysis transition: {expected_status} -> {next_status}")
        if commit_sha is not None:
            self._validate_commit_sha(commit_sha)
        is_failure = next_status == "failed"
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
            "status": next_status,
            "failure_code": failure_code,
            "failure_message": failure_message,
            "updated_at": func.now(),
            "finished_at": func.now() if is_failure else None,
            "version": AnalysisJobModel.version + 1,
        }
        if commit_sha is not None:
            values["commit_sha"] = commit_sha

        with self._sessions.begin() as session:
            result = session.execute(
                update(AnalysisJobModel)
                .where(
                    AnalysisJobModel.analysis_id == analysis_id,
                    AnalysisJobModel.status == expected_status,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                self._raise_transition_miss(session, analysis_id, expected_status)
            model = self._get_model(session, analysis_id)
            session.refresh(model)
            return self._snapshot(model)

    def complete_job(
        self,
        analysis_id: str,
        *,
        commit_sha: str,
        architecture: RepositoryArchitectureResponse | dict[str, object],
    ) -> StoredAnalysisJob:
        """Atomically persist the architecture and analyzing-to-completed transition."""

        self._validate_analysis_id(analysis_id)
        self._validate_commit_sha(commit_sha)
        try:
            validated = RepositoryArchitectureResponse.model_validate(architecture)
        except ValidationError as exc:
            raise ValueError("architecture does not match the v1 API contract") from exc
        payload = validated.model_dump(mode="json")

        try:
            with self._sessions.begin() as session:
                result = session.execute(
                    update(AnalysisJobModel)
                    .where(
                        AnalysisJobModel.analysis_id == analysis_id,
                        AnalysisJobModel.status == "analyzing",
                    )
                    .values(
                        status="completed",
                        commit_sha=commit_sha,
                        failure_code=None,
                        failure_message=None,
                        updated_at=func.now(),
                        finished_at=func.now(),
                        version=AnalysisJobModel.version + 1,
                    )
                )
                if result.rowcount != 1:
                    self._raise_transition_miss(session, analysis_id, "analyzing")
                session.add(
                    AnalysisArchitectureModel(
                        analysis_id=analysis_id,
                        schema_version=validated.schema_version,
                        payload=payload,
                    )
                )
                session.flush()
                model = self._get_model(session, analysis_id)
                session.refresh(model)
                snapshot = self._snapshot(model)
        except IntegrityError as exc:
            raise AnalysisTransitionConflict(
                "The analysis architecture was already persisted."
            ) from exc
        return snapshot

    def get_architecture(self, analysis_id: str) -> RepositoryArchitectureResponse:
        """Read and revalidate the artifact of one completed job."""

        self._validate_analysis_id(analysis_id)
        with self._sessions() as session:
            job = self._get_model(session, analysis_id)
            if job.status != "completed":
                raise StoredAnalysisNotCompleted(
                    "Architecture is available only after analysis completes."
                )
            artifact = session.get(AnalysisArchitectureModel, analysis_id)
            if artifact is None:
                raise AnalysisStorageCorrupt("Completed analysis has no architecture artifact.")
            try:
                return RepositoryArchitectureResponse.model_validate(artifact.payload)
            except ValidationError as exc:
                raise AnalysisStorageCorrupt(
                    "Stored architecture does not match its schema."
                ) from exc

    @staticmethod
    def _raise_transition_miss(
        session: Session,
        analysis_id: str,
        expected_status: AnalysisStatus,
    ) -> None:
        model = session.get(AnalysisJobModel, analysis_id)
        if model is None:
            raise StoredAnalysisNotFound("The analysis does not exist.")
        raise AnalysisTransitionConflict(
            f"Expected analysis status {expected_status}, found {model.status}."
        )
