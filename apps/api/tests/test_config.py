import pytest

from repolume_api.config import Settings


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError, match="REPOLUME_ENVIRONMENT"):
        Settings(environment="local")


def test_loads_analysis_runtime_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOLUME_ANALYSIS_RUNTIME_ENABLED", "true")

    assert Settings.from_environment().analysis_runtime_enabled is True


def test_rejects_invalid_analysis_runtime_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOLUME_ANALYSIS_RUNTIME_ENABLED", "sometimes")

    with pytest.raises(ValueError, match="must be true or false"):
        Settings.from_environment()
