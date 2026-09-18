"""Tests for Redis Stream analysis queue primitives."""

from typing import Any
from uuid import uuid4

import pytest
from redis.exceptions import ResponseError

from repolume_worker.analysis_queue import (
    QueueAcknowledgementConflict,
    QueueMessageError,
    RedisAnalysisQueue,
    WorkerQueueSettings,
    create_redis_client,
)


def _fields(**changes: str) -> dict[str, str]:
    fields = {
        "schema_version": "1.0",
        "event_id": str(uuid4()),
        "analysis_id": "analysis_123",
        "provider": "github",
        "owner": "octocat",
        "repository": "Hello-World",
        "ref": "main",
    }
    fields.update(changes)
    return fields


class FakeRedis:
    def __init__(self) -> None:
        self.group_error: ResponseError | None = None
        self.read_response: Any = []
        self.reclaim_response: Any = ["0-0", [], []]
        self.acknowledged = 1
        self.calls: list[tuple[str, Any]] = []

    def xgroup_create(self, name: str, groupname: str, id: str, mkstream: bool) -> bool:
        self.calls.append(("group", (name, groupname, id, mkstream)))
        if self.group_error is not None:
            raise self.group_error
        return True

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int | None,
        block: int | None,
    ) -> Any:
        self.calls.append(("read", (groupname, consumername, streams, count, block)))
        return self.read_response

    def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str,
        count: int | None,
    ) -> Any:
        self.calls.append(
            ("reclaim", (name, groupname, consumername, min_idle_time, start_id, count))
        )
        return self.reclaim_response

    def xack(self, name: str, groupname: str, *ids: str) -> int:
        self.calls.append(("ack", (name, groupname, ids)))
        return self.acknowledged


def test_settings_redact_credentials_and_load_client() -> None:
    settings = WorkerQueueSettings(url="rediss://worker:secret@redis.example:6380/2?x=1")
    connection_settings = create_redis_client(settings).connection_pool.connection_kwargs

    assert settings.safe_url == "rediss://worker:***@redis.example:6380/2"
    assert "secret" not in settings.safe_url
    assert "secret" not in repr(settings)
    assert connection_settings["decode_responses"]
    assert connection_settings["socket_connect_timeout"] == 5
    assert connection_settings["socket_timeout"] == 65


def test_settings_load_queue_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPOLUME_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REPOLUME_ANALYSIS_STREAM", "test:stream")
    monkeypatch.setenv("REPOLUME_ANALYSIS_CONSUMER_GROUP", "test-workers")
    monkeypatch.setenv("REPOLUME_ANALYSIS_CLAIM_IDLE_MS", "90000")

    settings = WorkerQueueSettings.from_environment()

    assert settings.stream_name == "test:stream"
    assert settings.consumer_group == "test-workers"
    assert settings.claim_idle_ms == 90_000


@pytest.mark.parametrize(
    "url",
    ["", "http://localhost", "redis:///0", "redis://localhost/0#fragment", "redis://host:bad"],
)
def test_settings_reject_invalid_redis_urls(url: str) -> None:
    with pytest.raises(ValueError):
        WorkerQueueSettings(url=url)


def test_creates_consumer_group_and_tolerates_existing_group() -> None:
    redis = FakeRedis()
    queue = RedisAnalysisQueue(redis)
    queue.ensure_consumer_group()
    redis.group_error = ResponseError("BUSYGROUP Consumer Group name already exists")

    queue.ensure_consumer_group()

    assert redis.calls[0] == (
        "group",
        ("repolume:analysis:requests", "repolume-workers", "0", True),
    )


def test_unexpected_group_creation_error_is_not_hidden() -> None:
    redis = FakeRedis()
    redis.group_error = ResponseError("NOAUTH Authentication required")

    with pytest.raises(ResponseError, match="NOAUTH"):
        RedisAnalysisQueue(redis).ensure_consumer_group()


def test_reads_and_validates_new_message() -> None:
    redis = FakeRedis()
    redis.read_response = [["repolume:analysis:requests", [["1-0", _fields()]]]]

    messages = RedisAnalysisQueue(redis).read("worker-1", count=2, block_ms=25)

    assert len(messages) == 1
    assert messages[0].analysis_id == "analysis_123"
    assert messages[0].ref == "main"
    assert redis.calls[-1] == (
        "read",
        ("repolume-workers", "worker-1", {"repolume:analysis:requests": ">"}, 2, 25),
    )


def test_empty_read_returns_empty_tuple() -> None:
    assert RedisAnalysisQueue(FakeRedis()).read("worker-1") == ()


def test_reclaims_stale_pending_message() -> None:
    redis = FakeRedis()
    redis.reclaim_response = ["0-0", [["2-0", _fields(ref="")]], []]

    messages = RedisAnalysisQueue(redis, claim_idle_ms=90_000).reclaim("worker-2")

    assert len(messages) == 1
    assert messages[0].ref is None
    assert redis.calls[-1][0] == "reclaim"
    assert redis.calls[-1][1][3] == 90_000


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"schema_version": "2.0"}, "queue_message_schema_invalid"),
        ({"event_id": "bad"}, "queue_event_id_invalid"),
        ({"analysis_id": "bad.id"}, "queue_analysis_id_invalid"),
        ({"provider": "gitlab"}, "queue_repository_invalid"),
        ({"repository": ""}, "queue_repository_invalid"),
        ({"owner": "bad--owner"}, "queue_repository_invalid"),
        ({"repository": ".."}, "queue_repository_invalid"),
        ({"ref": "../main"}, "queue_repository_invalid"),
    ],
)
def test_malformed_messages_raise_controlled_error(changes: dict[str, str], code: str) -> None:
    redis = FakeRedis()
    redis.read_response = [["repolume:analysis:requests", [["3-0", _fields(**changes)]]]]

    with pytest.raises(QueueMessageError) as raised:
        RedisAnalysisQueue(redis).read("worker-1")

    assert raised.value.message_id == "3-0"
    assert raised.value.code == code
    assert str(changes) not in str(raised.value)


def test_extra_fields_are_rejected() -> None:
    redis = FakeRedis()
    redis.read_response = [["repolume:analysis:requests", [["3-0", _fields(unexpected="value")]]]]

    with pytest.raises(QueueMessageError) as raised:
        RedisAnalysisQueue(redis).read("worker-1")

    assert raised.value.code == "queue_message_schema_invalid"


def test_acknowledges_processed_or_discarded_message() -> None:
    redis = FakeRedis()
    queue = RedisAnalysisQueue(redis)

    queue.acknowledge_id("4-0")

    assert redis.calls[-1] == (
        "ack",
        ("repolume:analysis:requests", "repolume-workers", ("4-0",)),
    )


def test_missing_acknowledgement_is_a_conflict() -> None:
    redis = FakeRedis()
    redis.acknowledged = 0

    with pytest.raises(QueueAcknowledgementConflict):
        RedisAnalysisQueue(redis).acknowledge_id("missing")


@pytest.mark.parametrize(("consumer", "count"), [("bad name", 1), ("worker", 0), ("worker", 101)])
def test_rejects_invalid_read_parameters(consumer: str, count: int) -> None:
    with pytest.raises(ValueError):
        RedisAnalysisQueue(FakeRedis()).read(consumer, count=count)


def test_invalid_claim_idle_environment_is_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPOLUME_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REPOLUME_ANALYSIS_CLAIM_IDLE_MS", "private-value")

    with pytest.raises(ValueError) as raised:
        WorkerQueueSettings.from_environment()

    assert "private-value" not in str(raised.value)


@pytest.mark.parametrize("block_ms", [-1, 60_001])
def test_rejects_invalid_block_times(block_ms: int) -> None:
    with pytest.raises(ValueError, match="between 0 and 60000"):
        RedisAnalysisQueue(FakeRedis()).read("worker", block_ms=block_ms)


def test_rejects_invalid_direct_claim_idle_time() -> None:
    with pytest.raises(ValueError, match="at least 1000"):
        RedisAnalysisQueue(FakeRedis(), claim_idle_ms=999)
