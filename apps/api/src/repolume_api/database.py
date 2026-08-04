"""Database configuration and engine construction."""

from dataclasses import dataclass, field
from os import getenv

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url

_DATABASE_ENV = "REPOLUME_DATABASE_URL"
_POSTGRESQL_DRIVER = "postgresql+psycopg"


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Validated database settings whose secret URL is never displayed."""

    url: URL = field(repr=False)

    def __post_init__(self) -> None:
        if self.url.drivername != _POSTGRESQL_DRIVER:
            raise ValueError(f"{_DATABASE_ENV} must use {_POSTGRESQL_DRIVER}")
        if not self.url.database:
            raise ValueError(f"{_DATABASE_ENV} must include a database name")

    @classmethod
    def from_url(cls, value: str) -> "DatabaseSettings":
        """Parse a PostgreSQL URL without including it in validation errors."""

        if not value:
            raise ValueError(f"{_DATABASE_ENV} is required")
        try:
            url = make_url(value)
        except Exception:
            raise ValueError(f"{_DATABASE_ENV} is invalid") from None
        return cls(url=url)

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        """Load the database URL from the process environment."""

        return cls.from_url(getenv(_DATABASE_ENV, ""))

    @property
    def safe_url(self) -> str:
        """Return a password-redacted URL suitable for diagnostics."""

        return self.url.render_as_string(hide_password=True)


def create_database_engine(settings: DatabaseSettings) -> Engine:
    """Create the production SQLAlchemy engine without opening a connection."""

    return create_engine(settings.url, pool_pre_ping=True)
