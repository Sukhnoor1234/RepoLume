import json
from io import StringIO

import pytest

import repolume_worker.cli as cli_module
from repolume_worker.cli import main
from repolume_worker.runtime import WorkerRunResult


def test_readiness_check_is_explicit_about_missing_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPOLUME_ENVIRONMENT", "test")
    output = StringIO()

    exit_code = main(["--check"], output=output)

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {
        "environment": "test",
        "event": "worker.ready",
        "queue_backend": "not_configured",
        "service": "repolume-worker",
        "version": "0.1.0",
    }


def test_readiness_reports_configured_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "REPOLUME_DATABASE_URL",
        "postgresql+psycopg://worker:secret@localhost/repolume",
    )
    monkeypatch.setenv("REPOLUME_REDIS_URL", "redis://worker:secret@localhost:6379/0")
    output = StringIO()

    assert main(["--check"], output=output) == 0
    assert json.loads(output.getvalue())["queue_backend"] == "redis_streams"
    assert "secret" not in output.getvalue()


def test_once_reports_safe_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "REPOLUME_DATABASE_URL",
        "postgresql+psycopg://worker:secret@localhost/repolume",
    )
    monkeypatch.setenv("REPOLUME_REDIS_URL", "redis://worker:secret@localhost:6379/0")
    monkeypatch.setattr(
        cli_module,
        "run_once_from_environment",
        lambda: WorkerRunResult("completed", "analysis_123"),
    )
    output = StringIO()

    assert main(["--once"], output=output) == 0
    assert json.loads(output.getvalue()) == {
        "analysis_id": "analysis_123",
        "environment": "development",
        "event": "worker.run_once",
        "outcome": "completed",
        "service": "repolume-worker",
        "version": "0.1.0",
    }
    assert "secret" not in output.getvalue()


def test_loop_delegates_to_long_running_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "REPOLUME_DATABASE_URL",
        "postgresql+psycopg://worker:secret@localhost/repolume",
    )
    monkeypatch.setenv("REPOLUME_REDIS_URL", "redis://worker:secret@localhost:6379/0")
    monkeypatch.setattr(
        cli_module,
        "run_loop_from_environment",
        lambda output=None: print(
            json.dumps({"event": "worker.loop.started", "leaked": False}),
            file=output,
        )
        or 0,
    )
    output = StringIO()

    assert main(["--loop"], output=output) == 0
    assert json.loads(output.getvalue()) == {
        "event": "worker.loop.started",
        "leaked": False,
    }
    assert "secret" not in output.getvalue()


def test_partial_runtime_configuration_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOLUME_DATABASE_URL", "private-value")

    with pytest.raises(ValueError) as raised:
        main(["--check"])

    assert "private-value" not in str(raised.value)
