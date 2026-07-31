import pytest

from repolume_worker.config import WorkerSettings


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError, match="REPOLUME_ENVIRONMENT"):
        WorkerSettings(environment="local")
