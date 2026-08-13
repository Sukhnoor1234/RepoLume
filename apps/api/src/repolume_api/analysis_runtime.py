"""Configured API runtime for durable submission and queue publication."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic
from typing import Protocol
from uuid import uuid4

from redis import Redis
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from repolume_api.analyses import (
    AnalysisJobSnapshot,
    AnalysisNotCompleted,
    AnalysisNotFound,
    AnalysisServiceUnavailable,
)
from repolume_api.analysis_outbox import (
    AnalysisOutboxStorage,
    RedisOutboxPublisher,
)
from repolume_api.analysis_schemas import RepositoryArchitectureResponse
from repolume_api.analysis_storage import (
    AnalysisStorage,
    AnalysisStorageError,
    StoredAnalysisJob,
    StoredAnalysisNotCompleted,
    StoredAnalysisNotFound,
)
from repolume_api.database import DatabaseSettings, create_database_engine
from repolume_api.queue import RedisQueueSettings, create_redis_client
from repolume_api.repositories import RepositoryReference

_LOGGER = logging.getLogger(__name__)


class OutboxPublisher(Protocol):
    """Publisher operation required by the retry loop."""

    def publish_batch(self, *, limit: int = 100) -> int: ...


class DatabaseAnalysisJobService:
    """Expose transactional storage through the HTTP job-service contract."""

    def __init__(
        self,
        storage: AnalysisStorage,
        *,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._storage = storage
        self._id_factory = id_factory or (lambda: f"analysis_{uuid4().hex}")

    @staticmethod
    def _snapshot(job: StoredAnalysisJob) -> AnalysisJobSnapshot:
        return AnalysisJobSnapshot(
            analysis_id=job.analysis_id,
            status=job.status,
            repository=job.repository,
            result_available=job.status == "completed",
            failure_code=job.failure_code,
            failure_message=job.failure_message,
        )

    def submit(self, repository: RepositoryReference) -> AnalysisJobSnapshot:
        try:
            job = self._storage.create_job(self._id_factory(), repository)
        except (AnalysisStorageError, SQLAlchemyError) as exc:
            raise AnalysisServiceUnavailable from exc
        return self._snapshot(job)

    def get(self, analysis_id: str) -> AnalysisJobSnapshot:
        try:
            return self._snapshot(self._storage.get_job(analysis_id))
        except StoredAnalysisNotFound as exc:
            raise AnalysisNotFound from exc
        except (AnalysisStorageError, SQLAlchemyError) as exc:
            raise AnalysisServiceUnavailable from exc

    def get_architecture(self, analysis_id: str) -> RepositoryArchitectureResponse:
        try:
            return self._storage.get_architecture(analysis_id)
        except StoredAnalysisNotFound as exc:
            raise AnalysisNotFound from exc
        except StoredAnalysisNotCompleted as exc:
            raise AnalysisNotCompleted from exc
        except (AnalysisStorageError, SQLAlchemyError) as exc:
            raise AnalysisServiceUnavailable from exc


class OutboxPublisherLoop:
    """Retry pending outbox events on a small stoppable background thread."""

    def __init__(
        self,
        publisher: OutboxPublisher,
        *,
        interval_seconds: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        if interval_seconds < 0.05:
            raise ValueError("publisher interval must be at least 0.05 seconds")
        if not 1 <= batch_size <= 100:
            raise ValueError("publisher batch size must be between 1 and 100")
        self._publisher = publisher
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    def run_once(self) -> int:
        return self._publisher.publish_batch(limit=self._batch_size)

    def _run(self) -> None:
        while not self._stop.is_set():
            started_at = monotonic()
            try:
                self.run_once()
            except Exception:
                _LOGGER.warning(
                    "Analysis outbox publication failed; the event remains retryable.",
                    extra={"event": "analysis.outbox.publish_failed"},
                )
            elapsed = monotonic() - started_at
            self._stop.wait(max(0.0, self._interval_seconds - elapsed))

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = Thread(
                target=self._run,
                name="repolume-outbox-publisher",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout_seconds: float = 10.0) -> None:
        self._stop.set()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout_seconds)
            if thread.is_alive():
                raise RuntimeError("Analysis outbox publisher did not stop in time.")


@dataclass(slots=True)
class AnalysisRuntime:
    """Owned API resources installed for one application process."""

    service: DatabaseAnalysisJobService
    publisher: OutboxPublisherLoop
    engine: Engine
    redis: Redis

    def start(self) -> None:
        self.publisher.start()

    def stop(self) -> None:
        try:
            self.publisher.stop()
        finally:
            self.redis.close()
            self.engine.dispose()


def create_analysis_runtime() -> AnalysisRuntime:
    """Build the production runtime from validated environment settings."""

    database_settings = DatabaseSettings.from_environment()
    queue_settings = RedisQueueSettings.from_environment()
    engine = create_database_engine(database_settings)
    redis = create_redis_client(queue_settings)
    storage = AnalysisStorage(engine)
    service = DatabaseAnalysisJobService(storage)
    publisher = OutboxPublisherLoop(
        RedisOutboxPublisher(
            AnalysisOutboxStorage(engine),
            redis,
            stream_name=queue_settings.stream_name,
        )
    )
    return AnalysisRuntime(service=service, publisher=publisher, engine=engine, redis=redis)
