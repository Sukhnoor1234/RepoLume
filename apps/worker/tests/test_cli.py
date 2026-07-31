import json
from io import StringIO

import pytest

from repolume_worker.cli import main


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
