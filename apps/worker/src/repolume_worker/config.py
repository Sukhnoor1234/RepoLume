"""Worker runtime configuration."""

from dataclasses import dataclass
from os import getenv

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    """Runtime settings that do not contain secrets."""

    environment: str = "development"
    service_name: str = "repolume-worker"

    def __post_init__(self) -> None:
        if self.environment not in ALLOWED_ENVIRONMENTS:
            allowed = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
            raise ValueError(f"REPOLUME_ENVIRONMENT must be one of: {allowed}")

    @classmethod
    def from_environment(cls) -> "WorkerSettings":
        """Load worker settings from environment variables."""

        return cls(environment=getenv("REPOLUME_ENVIRONMENT", "development"))
