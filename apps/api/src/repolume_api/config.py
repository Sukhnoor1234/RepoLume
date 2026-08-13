"""Application configuration."""

from dataclasses import dataclass
from os import getenv

ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings that are safe to expose in service metadata."""

    environment: str = "development"
    service_name: str = "repolume-api"
    analysis_runtime_enabled: bool = False

    def __post_init__(self) -> None:
        if self.environment not in ALLOWED_ENVIRONMENTS:
            allowed = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
            raise ValueError(f"REPOLUME_ENVIRONMENT must be one of: {allowed}")

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings from environment variables."""

        runtime_value = getenv("REPOLUME_ANALYSIS_RUNTIME_ENABLED", "false").lower()
        if runtime_value not in {"true", "false"}:
            raise ValueError("REPOLUME_ANALYSIS_RUNTIME_ENABLED must be true or false")
        return cls(
            environment=getenv("REPOLUME_ENVIRONMENT", "development"),
            analysis_runtime_enabled=runtime_value == "true",
        )
