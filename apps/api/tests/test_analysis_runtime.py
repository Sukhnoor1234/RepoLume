"""Tests for the configured API analysis runtime."""

from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from repolume_api.analyses import (
    AnalysisNotCompleted,
    AnalysisNotFound,
    AnalysisServiceUnavailable,
)
from repolume_api.analysis_runtime import DatabaseAnalysisJobService, OutboxPublisherLoop
from repolume_api.analysis_storage import AnalysisStorage
from repolume_api.config import Settings
from repolume_api.database_models import Base
from repolume_api.main import create_app
from repolume_api.repositories import RepositoryReference

_REPOSITORY = RepositoryReference(owner="octocat", repository="Hello-World", ref="main")


@pytest.fixture
def engine() -> Engine:
    database = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(database)
    try:
        yield database
    finally:
        Base.metadata.drop_all(database)
        database.dispose()


class FakePublisher:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[int] = []
        self.called = Event()

    def publish_batch(self, *, limit: int = 100) -> int:
        self.calls.append(limit)
        self.called.set()
        if self.failures:
            self.failures -= 1
            raise ConnectionError("private queue details")
        return 2


class FakeRuntime:
    def __init__(self, service: DatabaseAnalysisJobService) -> None:
        self.service = service
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1


def test_durable_service_submits_and_reads_job(engine: Engine) -> None:
    service = DatabaseAnalysisJobService(
        AnalysisStorage(engine), id_factory=lambda: "analysis_runtime"
    )

    submitted = service.submit(_REPOSITORY)
    loaded = service.get("analysis_runtime")

    assert submitted == loaded
    assert loaded.status == "queued"
    assert loaded.repository == _REPOSITORY


def test_durable_service_maps_storage_errors(engine: Engine) -> None:
    service = DatabaseAnalysisJobService(AnalysisStorage(engine), id_factory=lambda: "same_id")
    service.submit(_REPOSITORY)

    with pytest.raises(AnalysisServiceUnavailable):
        service.submit(_REPOSITORY)
    with pytest.raises(AnalysisNotFound):
        service.get("missing")
    with pytest.raises(AnalysisNotCompleted):
        service.get_architecture("same_id")


def test_http_routes_use_durable_service(engine: Engine) -> None:
    service = DatabaseAnalysisJobService(
        AnalysisStorage(engine), id_factory=lambda: "analysis_http"
    )

    with TestClient(
        create_app(Settings(environment="test"), analysis_job_service=service)
    ) as client:
        submitted = client.post(
            "/v1/analyses",
            json={"repository_url": "https://github.com/octocat/Hello-World", "ref": "main"},
        )
        inspected = client.get("/v1/analyses/analysis_http")

    assert submitted.status_code == 202
    assert submitted.json() == {"analysis_id": "analysis_http", "status": "queued"}
    assert inspected.status_code == 200
    assert inspected.json()["repository"]["canonical_url"] == _REPOSITORY.canonical_url


def test_publisher_loop_runs_configured_batch() -> None:
    publisher = FakePublisher()
    loop = OutboxPublisherLoop(publisher, batch_size=7)

    assert loop.run_once() == 2
    assert publisher.calls == [7]


def test_publisher_loop_retries_safely(caplog: pytest.LogCaptureFixture) -> None:
    publisher = FakePublisher(failures=1)
    loop = OutboxPublisherLoop(publisher, interval_seconds=0.05)

    loop.start()
    assert publisher.called.wait(1)
    publisher.called.clear()
    assert publisher.called.wait(1)
    loop.stop()

    assert len(publisher.calls) >= 2
    assert "private queue details" not in caplog.text
    assert "remains retryable" in caplog.text


def test_app_lifespan_owns_runtime(engine: Engine) -> None:
    service = DatabaseAnalysisJobService(
        AnalysisStorage(engine), id_factory=lambda: "analysis_runtime"
    )
    runtime = FakeRuntime(service)

    with TestClient(
        create_app(Settings(environment="test"), analysis_runtime=runtime)  # type: ignore[arg-type]
    ) as client:
        assert client.get("/health").status_code == 200
        assert runtime.started == 1

    assert runtime.stopped == 1


def test_app_rejects_two_runtime_adapters(engine: Engine) -> None:
    service = DatabaseAnalysisJobService(AnalysisStorage(engine))

    with pytest.raises(ValueError, match="either"):
        create_app(
            Settings(environment="test"),
            analysis_job_service=service,
            analysis_runtime=FakeRuntime(service),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(("interval", "batch"), [(0.01, 1), (1.0, 0), (1.0, 101)])
def test_publisher_loop_rejects_unsafe_settings(interval: float, batch: int) -> None:
    with pytest.raises(ValueError):
        OutboxPublisherLoop(FakePublisher(), interval_seconds=interval, batch_size=batch)
