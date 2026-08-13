"""One-message worker orchestration across Redis, analysis, and PostgreSQL."""

from dataclasses import dataclass
from typing import Literal, Protocol

from repolume_worker.analysis_queue import (
    AnalysisQueueMessage,
    QueueMessageError,
    RedisAnalysisQueue,
)
from repolume_worker.errors import AnalysisPipelineError
from repolume_worker.jobs import AnalysisJob, JobStatus
from repolume_worker.pipeline import (
    PipelineLifecycleObserver,
    PipelineStateConflict,
    PipelineStateUnavailable,
    RepositoryAnalysisPipeline,
)
from repolume_worker.retrieval import RepositoryRequest
from repolume_worker.runtime_storage import (
    WorkerAnalysisStorage,
    WorkerJobNotFound,
    WorkerStorageConflict,
)

WorkerOutcome = Literal["idle", "completed", "failed", "duplicate", "abandoned", "discarded"]


class AnalysisQueue(Protocol):
    def ensure_consumer_group(self) -> None: ...

    def read(
        self,
        consumer_name: str,
        *,
        count: int = 1,
        block_ms: int = 5_000,
    ) -> tuple[AnalysisQueueMessage, ...]: ...

    def reclaim(
        self,
        consumer_name: str,
        *,
        count: int = 10,
    ) -> tuple[AnalysisQueueMessage, ...]: ...

    def acknowledge(self, message: AnalysisQueueMessage) -> None: ...

    def acknowledge_id(self, message_id: str) -> None: ...


class AnalysisPipeline(Protocol):
    def run(
        self,
        job: AnalysisJob,
        request: RepositoryRequest,
        *,
        observer: PipelineLifecycleObserver | None = None,
    ): ...


@dataclass(frozen=True, slots=True)
class WorkerRunResult:
    """Safe operational result for one worker command invocation."""

    outcome: WorkerOutcome
    analysis_id: str | None = None


class PersistingLifecycleObserver:
    """Persist active pipeline transitions before expensive work continues."""

    def __init__(self, storage: WorkerAnalysisStorage, analysis_id: str) -> None:
        self._storage = storage
        self._analysis_id = analysis_id

    def _transition(
        self,
        expected_status: JobStatus,
        next_status: JobStatus,
        *,
        commit_sha: str | None = None,
    ) -> None:
        try:
            self._storage.transition(
                self._analysis_id,
                expected_status=expected_status,
                next_status=next_status,
                commit_sha=commit_sha,
            )
        except WorkerStorageConflict as exc:
            raise PipelineStateConflict from exc
        except Exception as exc:
            raise PipelineStateUnavailable from exc

    def on_cloning(self) -> None:
        self._transition(JobStatus.QUEUED, JobStatus.CLONING)

    def on_analyzing(self, commit_sha: str) -> None:
        self._transition(
            JobStatus.CLONING,
            JobStatus.ANALYZING,
            commit_sha=commit_sha,
        )


class AnalysisWorkerRuntime:
    """Process at most one recovered or new analysis queue message."""

    def __init__(
        self,
        queue: AnalysisQueue,
        storage: WorkerAnalysisStorage,
        pipeline: AnalysisPipeline,
    ) -> None:
        self._queue = queue
        self._storage = storage
        self._pipeline = pipeline

    def process_once(
        self,
        consumer_name: str,
        *,
        block_ms: int = 1_000,
    ) -> WorkerRunResult:
        self._queue.ensure_consumer_group()
        try:
            recovered = self._queue.reclaim(consumer_name, count=1)
        except QueueMessageError as exc:
            self._queue.acknowledge_id(exc.message_id)
            return WorkerRunResult("discarded")
        if recovered:
            return self._process_message(recovered[0], recovered=True)

        try:
            messages = self._queue.read(consumer_name, count=1, block_ms=block_ms)
        except QueueMessageError as exc:
            self._queue.acknowledge_id(exc.message_id)
            return WorkerRunResult("discarded")
        if not messages:
            return WorkerRunResult("idle")
        return self._process_message(messages[0], recovered=False)

    def _process_message(
        self,
        message: AnalysisQueueMessage,
        *,
        recovered: bool,
    ) -> WorkerRunResult:
        try:
            state = self._storage.get_job(message.analysis_id)
        except WorkerJobNotFound:
            self._queue.acknowledge(message)
            return WorkerRunResult("discarded", message.analysis_id)

        if state.status.is_terminal:
            self._queue.acknowledge(message)
            return WorkerRunResult("duplicate", message.analysis_id)
        if state.status is not JobStatus.QUEUED:
            if recovered:
                self._storage.transition(
                    message.analysis_id,
                    expected_status=state.status,
                    next_status=JobStatus.FAILED,
                    failure_code="analysis_abandoned",
                    failure_message="The previous analysis worker stopped before completion.",
                )
                self._queue.acknowledge(message)
                return WorkerRunResult("abandoned", message.analysis_id)
            self._queue.acknowledge(message)
            return WorkerRunResult("duplicate", message.analysis_id)

        observer = PersistingLifecycleObserver(self._storage, message.analysis_id)
        request = RepositoryRequest(
            owner=message.owner,
            repository=message.repository,
            ref=message.ref,
        )
        try:
            result = self._pipeline.run(
                AnalysisJob(message.analysis_id),
                request,
                observer=observer,
            )
        except PipelineStateConflict:
            self._queue.acknowledge(message)
            return WorkerRunResult("duplicate", message.analysis_id)
        except PipelineStateUnavailable:
            raise
        except AnalysisPipelineError as exc:
            expected_status = exc.transitions[-2]
            self._storage.transition(
                message.analysis_id,
                expected_status=expected_status,
                next_status=JobStatus.FAILED,
                failure_code=exc.code,
                failure_message=exc.message,
            )
            self._queue.acknowledge(message)
            return WorkerRunResult("failed", message.analysis_id)

        try:
            self._storage.complete(
                message.analysis_id,
                commit_sha=result.repository.commit_sha,
                architecture=result.architecture,
            )
        except WorkerStorageConflict:
            persisted = self._storage.get_job(message.analysis_id)
            if persisted.status is not JobStatus.COMPLETED:
                raise
        self._queue.acknowledge(message)
        return WorkerRunResult("completed", message.analysis_id)


def create_worker_runtime(
    queue: RedisAnalysisQueue,
    storage: WorkerAnalysisStorage,
    pipeline: RepositoryAnalysisPipeline,
) -> AnalysisWorkerRuntime:
    """Construct the concrete runtime while keeping tests dependency-injected."""

    return AnalysisWorkerRuntime(queue, storage, pipeline)
