"""Integration tests for transactional analysis storage."""

from copy import deepcopy
from os import getenv

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.exc import IntegrityError

from repolume_api.analysis_schemas import RepositoryArchitectureResponse
from repolume_api.analysis_storage import (
    AnalysisAlreadyExists,
    AnalysisStorage,
    AnalysisTransitionConflict,
    StoredAnalysisNotCompleted,
    StoredAnalysisNotFound,
)
from repolume_api.database_models import AnalysisJobModel, Base
from repolume_api.repositories import RepositoryReference

_REPOSITORY = RepositoryReference(owner="octocat", repository="Hello-World", ref="main")
_COMMIT_SHA = "a" * 40
_ARCHITECTURE = RepositoryArchitectureResponse.model_validate(
    {
        "schema_version": "1.0",
        "languages": [],
        "nodes": [
            {
                "id": "repository",
                "kind": "repository",
                "name": "repository",
                "language": None,
            }
        ],
        "edges": [],
        "diagnostics": [],
        "summary": {
            "language_count": 0,
            "node_count": 1,
            "edge_count": 0,
            "module_count": 0,
            "symbol_count": 0,
            "entry_point_count": 0,
            "external_dependency_count": 0,
            "dependency_count": 0,
            "diagnostic_count": 0,
        },
    }
)


@pytest.fixture
def engine() -> Engine:
    database_url = getenv("REPOLUME_TEST_DATABASE_URL", "sqlite://")
    database = create_engine(database_url)

    if database.dialect.name == "sqlite":

        @event.listens_for(database, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(database)
    try:
        yield database
    finally:
        Base.metadata.drop_all(database)
        database.dispose()


@pytest.fixture
def storage(engine: Engine) -> AnalysisStorage:
    return AnalysisStorage(engine)


def _create_analyzing(storage: AnalysisStorage, analysis_id: str = "analysis_123") -> None:
    storage.create_job(analysis_id, _REPOSITORY)
    storage.transition_job(
        analysis_id,
        expected_status="queued",
        next_status="cloning",
    )
    storage.transition_job(
        analysis_id,
        expected_status="cloning",
        next_status="analyzing",
        commit_sha=_COMMIT_SHA,
    )


def test_create_and_read_queued_job_across_repository_instances(engine: Engine) -> None:
    created = AnalysisStorage(engine).create_job("analysis_123", _REPOSITORY)
    loaded = AnalysisStorage(engine).get_job("analysis_123")

    assert created == loaded
    assert loaded.status == "queued"
    assert loaded.repository == _REPOSITORY
    assert loaded.commit_sha is None
    assert loaded.failure_code is None
    assert loaded.finished_at is None
    assert loaded.version == 1


def test_rejects_duplicate_analysis_id(storage: AnalysisStorage) -> None:
    storage.create_job("analysis_123", _REPOSITORY)

    with pytest.raises(AnalysisAlreadyExists):
        storage.create_job("analysis_123", _REPOSITORY)


def test_advances_lifecycle_with_compare_and_set(storage: AnalysisStorage) -> None:
    storage.create_job("analysis_123", _REPOSITORY)

    cloning = storage.transition_job(
        "analysis_123",
        expected_status="queued",
        next_status="cloning",
    )
    analyzing = storage.transition_job(
        "analysis_123",
        expected_status="cloning",
        next_status="analyzing",
        commit_sha=_COMMIT_SHA,
    )

    assert cloning.status == "cloning"
    assert cloning.version == 2
    assert analyzing.status == "analyzing"
    assert analyzing.commit_sha == _COMMIT_SHA
    assert analyzing.version == 3


def test_rejects_stale_or_skipped_lifecycle_updates(storage: AnalysisStorage) -> None:
    storage.create_job("analysis_123", _REPOSITORY)
    storage.transition_job(
        "analysis_123",
        expected_status="queued",
        next_status="cloning",
    )

    with pytest.raises(AnalysisTransitionConflict):
        storage.transition_job(
            "analysis_123",
            expected_status="queued",
            next_status="cloning",
        )
    with pytest.raises(ValueError, match="invalid analysis transition"):
        storage.transition_job(
            "analysis_123",
            expected_status="cloning",
            next_status="queued",
        )


def test_failed_transition_persists_only_safe_failure_fields(storage: AnalysisStorage) -> None:
    storage.create_job("analysis_123", _REPOSITORY)

    failed = storage.transition_job(
        "analysis_123",
        expected_status="queued",
        next_status="failed",
        failure_code="repository_not_found",
        failure_message="The GitHub repository or ref was not found.",
    )

    assert failed.status == "failed"
    assert failed.failure_code == "repository_not_found"
    assert failed.failure_message == "The GitHub repository or ref was not found."
    assert failed.finished_at is not None
    assert failed.version == 2


@pytest.mark.parametrize(
    ("failure_code", "failure_message"),
    [
        ("Unsafe-Code", "Safe message."),
        ("safe_code", " surrounding whitespace "),
        ("safe_code", "x" * 501),
    ],
)
def test_failed_transition_rejects_unsafe_or_unbounded_failure_fields(
    storage: AnalysisStorage,
    failure_code: str,
    failure_message: str,
) -> None:
    storage.create_job("analysis_123", _REPOSITORY)

    with pytest.raises(ValueError, match="safe, non-empty, and bounded"):
        storage.transition_job(
            "analysis_123",
            expected_status="queued",
            next_status="failed",
            failure_code=failure_code,
            failure_message=failure_message,
        )

    assert storage.get_job("analysis_123").status == "queued"


def test_failed_transition_requires_complete_failure_pair(storage: AnalysisStorage) -> None:
    storage.create_job("analysis_123", _REPOSITORY)

    with pytest.raises(ValueError, match="both safe failure fields"):
        storage.transition_job(
            "analysis_123",
            expected_status="queued",
            next_status="failed",
            failure_code="repository_not_found",
        )

    assert storage.get_job("analysis_123").status == "queued"


def test_completion_atomically_stores_architecture_and_commit(storage: AnalysisStorage) -> None:
    _create_analyzing(storage)

    completed = storage.complete_job(
        "analysis_123",
        commit_sha=_COMMIT_SHA,
        architecture=_ARCHITECTURE,
    )
    architecture = storage.get_architecture("analysis_123")

    assert completed.status == "completed"
    assert completed.commit_sha == _COMMIT_SHA
    assert completed.finished_at is not None
    assert completed.version == 4
    assert architecture == _ARCHITECTURE


def test_invalid_architecture_does_not_complete_job(storage: AnalysisStorage) -> None:
    _create_analyzing(storage)
    invalid = deepcopy(_ARCHITECTURE.model_dump(mode="json"))
    invalid["summary"]["node_count"] = -1

    with pytest.raises(ValueError, match="architecture does not match"):
        storage.complete_job(
            "analysis_123",
            commit_sha=_COMMIT_SHA,
            architecture=invalid,
        )

    assert storage.get_job("analysis_123").status == "analyzing"
    with pytest.raises(StoredAnalysisNotCompleted):
        storage.get_architecture("analysis_123")


def test_repeated_completion_is_rejected_without_overwrite(storage: AnalysisStorage) -> None:
    _create_analyzing(storage)
    storage.complete_job(
        "analysis_123",
        commit_sha=_COMMIT_SHA,
        architecture=_ARCHITECTURE,
    )

    changed = _ARCHITECTURE.model_copy(deep=True)
    with pytest.raises(AnalysisTransitionConflict):
        storage.complete_job(
            "analysis_123",
            commit_sha=_COMMIT_SHA,
            architecture=changed,
        )

    assert storage.get_architecture("analysis_123") == _ARCHITECTURE


def test_missing_job_has_controlled_error(storage: AnalysisStorage) -> None:
    with pytest.raises(StoredAnalysisNotFound):
        storage.get_job("missing")


def test_validates_identifiers_and_commit_shas_before_writes(storage: AnalysisStorage) -> None:
    with pytest.raises(ValueError, match="analysis_id"):
        storage.create_job("unsafe.id", _REPOSITORY)

    _create_analyzing(storage)
    with pytest.raises(ValueError, match="commit_sha"):
        storage.complete_job(
            "analysis_123",
            commit_sha="not-a-sha",
            architecture=_ARCHITECTURE,
        )
    assert storage.get_job("analysis_123").status == "analyzing"


def test_database_constraints_reject_invalid_failure_state(engine: Engine) -> None:
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(
            AnalysisJobModel(
                analysis_id="analysis_123",
                provider="github",
                owner="octocat",
                repository="Hello-World",
                canonical_url="https://github.com/octocat/Hello-World",
                requested_ref="main",
                status="failed",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
