"""Redis Stream consumer primitives for analysis request delivery."""

import re
from dataclasses import dataclass, field
from os import getenv
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from redis import Redis
from redis.exceptions import ResponseError

_ANALYSIS_ID = re.compile(r"[A-Za-z0-9_-]{1,64}", re.ASCII)
_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", re.ASCII)
_REPOSITORY = re.compile(r"[A-Za-z0-9._-]{1,100}", re.ASCII)
_REF = re.compile(r"[A-Za-z0-9._/-]{1,255}", re.ASCII)
_CONSUMER_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}", re.ASCII)


class QueueMessageError(ValueError):
    """Controlled malformed-message error without submitted field contents."""

    def __init__(self, message_id: str, code: str) -> None:
        super().__init__("Analysis queue message is invalid.")
        self.message_id = message_id
        self.code = code


class QueueAcknowledgementConflict(RuntimeError):
    """Raised when a pending message is no longer owned by this group."""


@dataclass(frozen=True, slots=True)
class WorkerQueueSettings:
    """Validated worker Redis settings with credentials excluded from repr."""

    url: str = field(repr=False)
    stream_name: str = "repolume:analysis:requests"
    consumer_group: str = "repolume-workers"
    claim_idle_ms: int = 60_000

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.url)
            _ = parsed.port
        except ValueError:
            raise ValueError("REPOLUME_REDIS_URL is invalid") from None
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("REPOLUME_REDIS_URL must use redis:// or rediss://")
        if parsed.fragment:
            raise ValueError("REPOLUME_REDIS_URL cannot include a fragment")
        if not self.stream_name or len(self.stream_name) > 128:
            raise ValueError("Redis stream name must contain 1 to 128 characters")
        if not self.consumer_group or len(self.consumer_group) > 128:
            raise ValueError("Redis consumer group must contain 1 to 128 characters")
        if self.claim_idle_ms < 1_000:
            raise ValueError("Redis claim idle time must be at least 1000 milliseconds")

    @classmethod
    def from_environment(cls) -> "WorkerQueueSettings":
        url = getenv("REPOLUME_REDIS_URL", "")
        if not url:
            raise ValueError("REPOLUME_REDIS_URL is required")
        try:
            claim_idle_ms = int(getenv("REPOLUME_ANALYSIS_CLAIM_IDLE_MS", "60000"))
        except ValueError:
            raise ValueError("REPOLUME_ANALYSIS_CLAIM_IDLE_MS must be an integer") from None
        return cls(
            url=url,
            stream_name=getenv("REPOLUME_ANALYSIS_STREAM", "repolume:analysis:requests"),
            consumer_group=getenv("REPOLUME_ANALYSIS_CONSUMER_GROUP", "repolume-workers"),
            claim_idle_ms=claim_idle_ms,
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


@dataclass(frozen=True, slots=True)
class AnalysisQueueMessage:
    """Validated request claimed from the analysis stream."""

    message_id: str
    event_id: str
    analysis_id: str
    provider: str
    owner: str
    repository: str
    ref: str | None


class RedisStreamReader(Protocol):
    def xgroup_create(
        self, name: str, groupname: str, id: str = "0", mkstream: bool = False
    ) -> Any: ...

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> Any: ...

    def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str = "0-0",
        count: int | None = None,
    ) -> Any: ...

    def xack(self, name: str, groupname: str, *ids: str) -> int: ...


class RedisAnalysisQueue:
    """Claim, recover, and acknowledge Redis Stream messages."""

    def __init__(
        self,
        redis: RedisStreamReader,
        *,
        stream_name: str = "repolume:analysis:requests",
        consumer_group: str = "repolume-workers",
        claim_idle_ms: int = 60_000,
    ) -> None:
        self._redis = redis
        self._stream_name = stream_name
        self._consumer_group = consumer_group
        if claim_idle_ms < 1_000:
            raise ValueError("queue claim idle time must be at least 1000 milliseconds")
        self._claim_idle_ms = claim_idle_ms

    def ensure_consumer_group(self) -> None:
        """Create the group and stream once, tolerating an existing group."""

        try:
            self._redis.xgroup_create(
                self._stream_name,
                self._consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def read(
        self,
        consumer_name: str,
        *,
        count: int = 1,
        block_ms: int = 5_000,
    ) -> tuple[AnalysisQueueMessage, ...]:
        self._validate_request(consumer_name, count)
        if not 0 <= block_ms <= 60_000:
            raise ValueError("queue block time must be between 0 and 60000 milliseconds")
        response = self._redis.xreadgroup(
            self._consumer_group,
            consumer_name,
            {self._stream_name: ">"},
            count=count,
            block=block_ms,
        )
        return self._parse_stream_response(response)

    def reclaim(
        self,
        consumer_name: str,
        *,
        count: int = 10,
    ) -> tuple[AnalysisQueueMessage, ...]:
        self._validate_request(consumer_name, count)
        response = self._redis.xautoclaim(
            self._stream_name,
            self._consumer_group,
            consumer_name,
            self._claim_idle_ms,
            start_id="0-0",
            count=count,
        )
        messages = response[1] if response else []
        return tuple(self._parse_message(message_id, fields) for message_id, fields in messages)

    def acknowledge(self, message: AnalysisQueueMessage) -> None:
        self.acknowledge_id(message.message_id)

    def acknowledge_id(self, message_id: str) -> None:
        """Acknowledge processed or intentionally discarded malformed delivery."""

        if self._redis.xack(self._stream_name, self._consumer_group, message_id) != 1:
            raise QueueAcknowledgementConflict("Analysis queue acknowledgement was not applied.")

    @staticmethod
    def _validate_request(consumer_name: str, count: int) -> None:
        if not _CONSUMER_NAME.fullmatch(consumer_name):
            raise ValueError("consumer name must contain 1 to 64 safe characters")
        if not 1 <= count <= 100:
            raise ValueError("queue read count must be between 1 and 100")

    def _parse_stream_response(self, response: Any) -> tuple[AnalysisQueueMessage, ...]:
        if not response:
            return ()
        messages: list[AnalysisQueueMessage] = []
        for _stream, entries in response:
            messages.extend(
                self._parse_message(message_id, fields) for message_id, fields in entries
            )
        return tuple(messages)

    @staticmethod
    def _parse_message(message_id: str, fields: dict[str, str]) -> AnalysisQueueMessage:
        required = {
            "schema_version",
            "event_id",
            "analysis_id",
            "provider",
            "owner",
            "repository",
            "ref",
        }
        if set(fields) != required or fields.get("schema_version") != "1.0":
            raise QueueMessageError(message_id, "queue_message_schema_invalid")
        try:
            UUID(fields["event_id"])
        except (ValueError, AttributeError):
            raise QueueMessageError(message_id, "queue_event_id_invalid") from None
        if not _ANALYSIS_ID.fullmatch(fields["analysis_id"]):
            raise QueueMessageError(message_id, "queue_analysis_id_invalid")
        owner = fields["owner"]
        repository = fields["repository"]
        ref = fields["ref"] or None
        ref_parts = ref.split("/") if ref is not None else []
        repository_is_invalid = (
            fields["provider"] != "github"
            or not _OWNER.fullmatch(owner)
            or "--" in owner
            or not _REPOSITORY.fullmatch(repository)
            or repository in {".", ".."}
            or (
                ref is not None
                and (
                    not _REF.fullmatch(ref)
                    or ref.startswith(("-", "/"))
                    or ref.endswith(("/", "."))
                    or ".." in ref
                    or "//" in ref
                    or "@{" in ref
                    or ref == "@"
                    or any(part.startswith(".") or part.endswith(".lock") for part in ref_parts)
                )
            )
        )
        if repository_is_invalid:
            raise QueueMessageError(message_id, "queue_repository_invalid")
        return AnalysisQueueMessage(
            message_id=message_id,
            event_id=fields["event_id"],
            analysis_id=fields["analysis_id"],
            provider=fields["provider"],
            owner=fields["owner"],
            repository=fields["repository"],
            ref=ref,
        )


def create_redis_client(settings: WorkerQueueSettings) -> Redis:
    """Create a decoded Redis client without opening a connection."""

    return Redis.from_url(settings.url, decode_responses=True)
