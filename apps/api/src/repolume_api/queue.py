"""Redis queue configuration shared by API publication adapters."""

from dataclasses import dataclass, field
from os import getenv
from urllib.parse import urlsplit, urlunsplit

from redis import Redis

_REDIS_ENV = "REPOLUME_REDIS_URL"


@dataclass(frozen=True, slots=True)
class RedisQueueSettings:
    """Validated Redis Stream settings with a secret-safe representation."""

    url: str = field(repr=False)
    stream_name: str = "repolume:analysis:requests"

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.url)
            _ = parsed.port
        except ValueError:
            raise ValueError(f"{_REDIS_ENV} is invalid") from None
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError(f"{_REDIS_ENV} must use redis:// or rediss://")
        if parsed.fragment:
            raise ValueError(f"{_REDIS_ENV} cannot include a fragment")
        if not self.stream_name or len(self.stream_name) > 128:
            raise ValueError("Redis stream name must contain 1 to 128 characters")

    @classmethod
    def from_url(
        cls, url: str, *, stream_name: str = "repolume:analysis:requests"
    ) -> "RedisQueueSettings":
        if not url:
            raise ValueError(f"{_REDIS_ENV} is required")
        return cls(url=url, stream_name=stream_name)

    @classmethod
    def from_environment(cls) -> "RedisQueueSettings":
        return cls.from_url(
            getenv(_REDIS_ENV, ""),
            stream_name=getenv("REPOLUME_ANALYSIS_STREAM", "repolume:analysis:requests"),
        )

    @property
    def safe_url(self) -> str:
        parsed = urlsplit(self.url)
        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port is not None else ""
        username = parsed.username or ""
        credentials = ""
        if username:
            credentials = f"{username}:***@" if parsed.password is not None else f"{username}@"
        return urlunsplit((parsed.scheme, f"{credentials}{hostname}{port}", parsed.path, "", ""))


def create_redis_client(settings: RedisQueueSettings) -> Redis:
    """Create a decoded Redis client without opening a connection."""

    return Redis.from_url(settings.url, decode_responses=True)
