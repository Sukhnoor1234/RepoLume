"""Tests for worker lifecycle persistence against the shared schema."""

import pytest
from sqlalchemy import Engine, create_engine, insert, select

from repolume_worker.analysis_models import Confidence, SourceLocation
from repolume_worker.architecture_models import (
    ArchitectureEdge,
    ArchitectureEdgeKind,
    ArchitectureNode,
    ArchitectureNodeKind,
    ArchitectureSummary,
    RepositoryArchitectureArtifact,
)
from repolume_worker.jobs import JobStatus
from repolume_worker.runtime_storage import (
    WorkerAnalysisStorage,
    WorkerStorageConflict,
    analysis_architectures,
    analysis_jobs,
    metadata,
)

_COMMIT_SHA = "a" * 40
_ARCHITECTURE = RepositoryArchitectureArtifact(
    schema_version="1.0",
    languages=("python",),
    nodes=(
        ArchitectureNode(
            id="repository",
            kind=ArchitectureNodeKind.REPOSITORY,
            name="repository",
            language=None,
        ),
        ArchitectureNode(
            id="module:app",
            kind=ArchitectureNodeKind.MODULE,
            name="app",
            language="python",
            location=SourceLocation("app.py", 1, 2),
        ),
    ),
    edges=(
        ArchitectureEdge(
            id="contains:repository:module:app",
            kind=ArchitectureEdgeKind.CONTAINS,
            source="repository",
            target="module:app",
            confidence=Confidence.CONFIRMED,
            location=SourceLocation("app.py", 1, 2),
        ),
    ),
    diagnostics=(),
    summary=ArchitectureSummary(
        language_count=1,
        node_count=2,
        edge_count=1,
        module_count=1,
        symbol_count=0,
        entry_point_count=0,
        external_dependency_count=0,
        dependency_count=0,
        diagnostic_count=0,
    ),
)


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    return engine


def _insert_job(engine: Engine, analysis_id: str = "analysis_123", status: str = "queued") -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(analysis_jobs).values(
                analysis_id=analysis_id,
                provider="github",
                owner="octocat",
                repository="Hello-World",
                canonical_url="https://github.com/octocat/Hello-World",
                requested_ref="main",
                status=status,
                version=1,
            )
        )


def test_persists_active_transitions_and_completed_architecture() -> None:
    engine = _engine()
    _insert_job(engine)
    storage = WorkerAnalysisStorage(engine)
    try:
        cloning = storage.transition(
            "analysis_123",
            expected_status=JobStatus.QUEUED,
            next_status=JobStatus.CLONING,
        )
        analyzing = storage.transition(
            "analysis_123",
            expected_status=JobStatus.CLONING,
            next_status=JobStatus.ANALYZING,
            commit_sha=_COMMIT_SHA,
        )
        completed = storage.complete(
            "analysis_123",
            commit_sha=_COMMIT_SHA,
            architecture=_ARCHITECTURE,
        )
        with engine.connect() as connection:
            payload = connection.scalar(select(analysis_architectures.c.payload))

        assert cloning.status is JobStatus.CLONING
        assert analyzing.status is JobStatus.ANALYZING
        assert analyzing.commit_sha == _COMMIT_SHA
        assert completed.status is JobStatus.COMPLETED
        assert payload["summary"]["node_count"] == 2
        assert payload["nodes"][1]["location"]["path"] == "app.py"
    finally:
        engine.dispose()


def test_rejects_stale_transition() -> None:
    engine = _engine()
    _insert_job(engine, status="cloning")
    storage = WorkerAnalysisStorage(engine)
    try:
        with pytest.raises(WorkerStorageConflict):
            storage.transition(
                "analysis_123",
                expected_status=JobStatus.QUEUED,
                next_status=JobStatus.CLONING,
            )
    finally:
        engine.dispose()


def test_persists_safe_failure() -> None:
    engine = _engine()
    _insert_job(engine, status="analyzing")
    storage = WorkerAnalysisStorage(engine)
    try:
        failed = storage.transition(
            "analysis_123",
            expected_status=JobStatus.ANALYZING,
            next_status=JobStatus.FAILED,
            failure_code="analysis_failed",
            failure_message="Repository analysis could not be completed.",
        )
        with engine.connect() as connection:
            row = connection.execute(
                select(
                    analysis_jobs.c.failure_code,
                    analysis_jobs.c.failure_message,
                    analysis_jobs.c.finished_at,
                )
            ).one()

        assert failed.status is JobStatus.FAILED
        assert row.failure_code == "analysis_failed"
        assert row.failure_message == "Repository analysis could not be completed."
        assert row.finished_at is not None
    finally:
        engine.dispose()
