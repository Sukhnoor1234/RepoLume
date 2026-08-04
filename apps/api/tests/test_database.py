"""Tests for database configuration, metadata, and migrations."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import JSON
from sqlalchemy.dialects import postgresql

from repolume_api.database import DatabaseSettings, create_database_engine
from repolume_api.database_models import AnalysisArchitectureModel, Base

_API_ROOT = Path(__file__).parents[1]


def test_database_settings_accept_postgresql_psycopg_and_redact_password() -> None:
    settings = DatabaseSettings.from_url(
        "postgresql+psycopg://repolume:redaction-check@db.example/repolume"
    )

    assert settings.url.drivername == "postgresql+psycopg"
    assert settings.url.database == "repolume"
    assert settings.safe_url == "postgresql+psycopg://repolume:***@db.example/repolume"
    assert "redaction-check" not in settings.safe_url
    assert "redaction-check" not in repr(settings)


def test_database_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "REPOLUME_DATABASE_URL",
        "postgresql+psycopg://repolume:secret@localhost/repolume",
    )

    settings = DatabaseSettings.from_environment()

    assert settings.url.host == "localhost"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sqlite:///local.db",
        "postgresql://user:secret@localhost/repolume",
        "postgresql+psycopg://user:secret@localhost",
        "not a database URL",
    ],
)
def test_database_settings_reject_invalid_urls_without_echoing_them(value: str) -> None:
    with pytest.raises(ValueError) as raised:
        DatabaseSettings.from_url(value)

    if value:
        assert value not in str(raised.value)
    assert "secret" not in str(raised.value)


def test_engine_creation_does_not_open_a_connection() -> None:
    settings = DatabaseSettings.from_url(
        "postgresql+psycopg://repolume:secret@unreachable.invalid/repolume"
    )

    engine = create_database_engine(settings)

    assert engine.url.database == "repolume"
    engine.dispose()


def test_models_define_expected_tables_and_postgresql_jsonb() -> None:
    assert set(Base.metadata.tables) == {"analysis_jobs", "analysis_architectures"}
    payload_type = AnalysisArchitectureModel.__table__.c.payload.type

    assert isinstance(payload_type, JSON)
    assert isinstance(payload_type.dialect_impl(postgresql.dialect()), postgresql.JSONB)


def test_alembic_has_one_linear_head() -> None:
    config = Config(_API_ROOT / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["0001_analysis_storage"]
    assert scripts.get_base() == "0001_analysis_storage"
