"""Tests for worker database configuration."""

import pytest

from repolume_worker.database import WorkerDatabaseSettings, create_database_engine


def test_accepts_postgresql_url_and_redacts_password() -> None:
    settings = WorkerDatabaseSettings.from_url(
        "postgresql+psycopg://worker:very-secret@db.example/repolume"
    )

    assert settings.safe_url == "postgresql+psycopg://worker:***@db.example/repolume"
    assert "very-secret" not in settings.safe_url
    assert "very-secret" not in repr(settings)


def test_engine_creation_does_not_connect() -> None:
    settings = WorkerDatabaseSettings.from_url(
        "postgresql+psycopg://worker:secret@unreachable.invalid/repolume"
    )

    engine = create_database_engine(settings)

    assert engine.url.database == "repolume"
    engine.dispose()


@pytest.mark.parametrize(
    "value",
    ["", "sqlite:///local.db", "postgresql://user:secret@localhost/repolume"],
)
def test_rejects_invalid_urls_without_echoing_them(value: str) -> None:
    with pytest.raises(ValueError) as raised:
        WorkerDatabaseSettings.from_url(value)

    if value:
        assert value not in str(raised.value)
