"""Tests for one-message worker runtime orchestration."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, insert

from repolume_worker.analysis_queue import AnalysisQueueMessage, QueueMessageError
from repolume_worker.architecture import RepositoryArchitectureComposer
from repolume_worker.errors import AnalysisPipelineError
from repolume_worker.jobs import JobStatus
from repolume_worker.pipeline import PipelineStateConflict
from repolume_worker.runtime import AnalysisWorkerRuntime
from repolume_worker.runtime_storage import (
    WorkerAnalysisStorage,
    analysis_jobs,
    metadata,
)

_COMMIT_SHA = "a" * 40


def _engine(status: str = "queued") -> Engine:
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(analysis_jobs).values(
                analysis_id="analysis_123",
                provider="github",
                owner="octocat",
                repository="Hello-World",
                canonical_url="https://github.com/octocat/Hello-World",
                requested_ref="main",
                status=status,
                version=1,
            )
        )
    return engine


def _message() -> AnalysisQueueMessage:
    return AnalysisQueueMessage(
        message_id="1-0",
        event_id=str(uuid4()),
        analysis_id="analysis_123",
        provider="github",
        owner="octocat",
        repository="Hello-World",
        ref="main",
    )


class FakeQueue:
    def __init__(
        self,
        *,
        new: tuple[AnalysisQueueMessage, ...] = (),
        recovered: tuple[AnalysisQueueMessage, ...] = (),
        reclaim_error: QueueMessageError | None = None,
    ) -> None:
        self.new = new
        self.recovered = recovered
        self.reclaim_error = reclaim_error
        self.ensured = 0
        self.acknowledged: list[str] = []

    def ensure_consumer_group(self) -> None:
        self.ensured += 1

    def reclaim(self, _consumer: str, *, count: int = 10):
        assert count == 1
        if self.reclaim_error is not None:
            raise self.reclaim_error
        return self.recovered

    def read(self, _consumer: str, *, count: int = 1, block_ms: int = 5_000):
        assert count == 1
        assert block_ms == 25
        return self.new

    def acknowledge(self, message: AnalysisQueueMessage) -> None:
        self.acknowledged.append(message.message_id)

    def acknowledge_id(self, message_id: str) -> None:
        self.acknowledged.append(message_id)


class FakePipeline:
    def __init__(self, *, failure: bool = False, conflict: bool = False) -> None:
        self.failure = failure
        self.conflict = conflict
        self.calls = 0

    def run(self, job, request, *, observer=None):
        self.calls += 1
        if self.conflict:
            raise PipelineStateConflict
        assert request.owner == "octocat"
        assert observer is not None
        observer.on_cloning()
        observer.on_analyzing(_COMMIT_SHA)
        if self.failure:
            raise AnalysisPipelineError(
                analysis_id=job.analysis_id,
                code="analysis_failed",
                message="Repository analysis could not be completed.",
                transitions=(
                    JobStatus.QUEUED,
                    JobStatus.CLONING,
                    JobStatus.ANALYZING,
                    JobStatus.FAILED,
                ),
            )
        return SimpleNamespace(
            repository=SimpleNamespace(commit_sha=_COMMIT_SHA),
            architecture=RepositoryArchitectureComposer().compose(()),
        )


def test_processes_new_message_to_durable_completion() -> None:
    engine = _engine()
    queue = FakeQueue(new=(_message(),))
    pipeline = FakePipeline()
    storage = WorkerAnalysisStorage(engine)
    try:
        result = AnalysisWorkerRuntime(queue, storage, pipeline).process_once(
            "worker-1", block_ms=25
        )

        assert result.outcome == "completed"
        assert result.analysis_id == "analysis_123"
        assert storage.get_job("analysis_123").status is JobStatus.COMPLETED
        assert queue.acknowledged == ["1-0"]
        assert pipeline.calls == 1
    finally:
        engine.dispose()


def test_persists_pipeline_failure_before_acknowledgement() -> None:
    engine = _engine()
    queue = FakeQueue(new=(_message(),))
    storage = WorkerAnalysisStorage(engine)
    try:
        result = AnalysisWorkerRuntime(queue, storage, FakePipeline(failure=True)).process_once(
            "worker-1", block_ms=25
        )

        assert result.outcome == "failed"
        assert storage.get_job("analysis_123").status is JobStatus.FAILED
        assert queue.acknowledged == ["1-0"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("status", ["completed", "failed", "cloning", "analyzing"])
def test_new_duplicate_does_not_rerun_pipeline(status: str) -> None:
    engine = _engine(status)
    queue = FakeQueue(new=(_message(),))
    pipeline = FakePipeline()
    try:
        result = AnalysisWorkerRuntime(queue, WorkerAnalysisStorage(engine), pipeline).process_once(
            "worker-1", block_ms=25
        )

        assert result.outcome == "duplicate"
        assert pipeline.calls == 0
        assert queue.acknowledged == ["1-0"]
    finally:
        engine.dispose()


def test_recovered_active_job_is_failed_safely() -> None:
    engine = _engine("analyzing")
    queue = FakeQueue(recovered=(_message(),))
    storage = WorkerAnalysisStorage(engine)
    try:
        result = AnalysisWorkerRuntime(queue, storage, FakePipeline()).process_once(
            "worker-1", block_ms=25
        )

        assert result.outcome == "abandoned"
        assert storage.get_job("analysis_123").status is JobStatus.FAILED
        assert queue.acknowledged == ["1-0"]
    finally:
        engine.dispose()


def test_pipeline_claim_conflict_is_acknowledged_as_duplicate() -> None:
    engine = _engine()
    queue = FakeQueue(new=(_message(),))
    try:
        result = AnalysisWorkerRuntime(
            queue,
            WorkerAnalysisStorage(engine),
            FakePipeline(conflict=True),
        ).process_once("worker-1", block_ms=25)

        assert result.outcome == "duplicate"
        assert queue.acknowledged == ["1-0"]
    finally:
        engine.dispose()


def test_missing_job_is_discarded() -> None:
    engine = _engine()
    with engine.begin() as connection:
        connection.execute(analysis_jobs.delete())
    queue = FakeQueue(new=(_message(),))
    try:
        result = AnalysisWorkerRuntime(
            queue, WorkerAnalysisStorage(engine), FakePipeline()
        ).process_once("worker-1", block_ms=25)

        assert result.outcome == "discarded"
        assert queue.acknowledged == ["1-0"]
    finally:
        engine.dispose()


def test_malformed_recovered_message_is_discarded_by_id() -> None:
    queue = FakeQueue(reclaim_error=QueueMessageError("bad-1", "invalid"))
    engine = _engine()
    try:
        result = AnalysisWorkerRuntime(
            queue, WorkerAnalysisStorage(engine), FakePipeline()
        ).process_once("worker-1", block_ms=25)

        assert result.outcome == "discarded"
        assert queue.acknowledged == ["bad-1"]
    finally:
        engine.dispose()


def test_empty_queue_returns_idle() -> None:
    queue = FakeQueue()
    engine = _engine()
    try:
        result = AnalysisWorkerRuntime(
            queue, WorkerAnalysisStorage(engine), FakePipeline()
        ).process_once("worker-1", block_ms=25)

        assert result.outcome == "idle"
        assert queue.acknowledged == []
    finally:
        engine.dispose()
