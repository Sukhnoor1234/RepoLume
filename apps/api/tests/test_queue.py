"""Tests for secret-safe Redis queue configuration."""

import pytest

from repolume_api.queue import RedisQueueSettings, create_redis_client


def test_settings_accept_redis_url_and_redact_password() -> None:
    settings = RedisQueueSettings.from_url(
        "rediss://repolume:very-secret@redis.example:6380/2?ssl_cert_reqs=required"
    )

    assert settings.safe_url == "rediss://repolume:***@redis.example:6380/2"
    assert "very-secret" not in settings.safe_url
    assert "very-secret" not in repr(settings)


def test_settings_load_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOLUME_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REPOLUME_ANALYSIS_STREAM", "test:analysis")

    settings = RedisQueueSettings.from_environment()

    assert settings.stream_name == "test:analysis"
    assert create_redis_client(settings).connection_pool.connection_kwargs["decode_responses"]


@pytest.mark.parametrize(
    "url",
    ["", "http://localhost", "redis:///0", "redis://localhost/0#secret", "redis://host:bad/0"],
)
def test_settings_reject_invalid_urls_without_echoing_them(url: str) -> None:
    with pytest.raises(ValueError) as raised:
        RedisQueueSettings.from_url(url)

    if url:
        assert url not in str(raised.value)
