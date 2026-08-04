"""Tests for transactional outbox storage and Redis Stream publication."""

from datetime import UTC, datetime, timedelta
from os import getenv

import pytest
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session

from repolume_api.analysis_outbox import (
    AnalysisOutboxStorage,
    OutboxClaimConflict,
    OutboxPublishError,
    RedisOutboxPublisher,
)
from repolume_api.analysis_storage import AnalysisAlreadyExists, AnalysisStorage
from repolume_api.database_models import AnalysisOutboxModel, Base
from repolume_api.repositories import RepositoryReference

_REPOSITORY = RepositoryReference(owner="octocat", repository="Hello-World", ref="main")


@pytest.fixture
def engine() -> Engine:
    database = create_engine(getenv("REPOLUME_TEST_DATABASE_URL", "sqlite://"))
    if database.dialect.name == "sqlite":

        @event.listens_for(database, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(database)
    try:
        yield database
    finally:
        Base.metadata.drop_all(database)
        database.dispose()


class FakeRedis:
    def __init__(
        self,
        *,
        fail: bool = False,
        fail_after: int | None = None,
        return_bytes: bool = False,
    ) -> None:
        self.fail = fail
        self.fail_after = fail_after
        self.return_bytes = return_bytes
        self.published: list[tuple[str, dict[str, str]]] = []

    def xadd(self, name: str, fields: dict[str, str]) -> str | bytes:
        if self.fail or (self.fail_after is not None and len(self.published) >= self.fail_after):
            raise ConnectionError("private Redis detail")
        self.published.append((name, fields))
        return b"1710000000000-0" if self.return_bytes else "1710000000000-0"


def _create_event(engine: Engine) -> AnalysisOutboxStorage:
    AnalysisStorage(engine).create_job("analysis_123", _REPOSITORY)
    return AnalysisOutboxStorage(engine)


def test_job_and_request_event_are_created_atomically(engine: Engine) -> None:
    storage = AnalysisStorage(engine)
    storage.create_job("analysis_123", _REPOSITORY)

    with Session(engine) as session:
        event = session.scalar(select(AnalysisOutboxModel))

    assert event is not None
    assert event.analysis_id == "analysis_123"
    assert event.event_type == "analysis_requested"
    assert event.payload == {
        "schema_version": "1.0",
        "analysis_id": "analysis_123",
        "provider": "github",
        "owner": "octocat",
        "repository": "Hello-World",
        "ref": "main",
    }
    assert event.publish_attempts == 0
    assert event.published_at is None


def test_duplicate_job_rolls_back_duplicate_event(engine: Engine) -> None:
    storage = AnalysisStorage(engine)
    storage.create_job("analysis_123", _REPOSITORY)

    with pytest.raises(AnalysisAlreadyExists):
        storage.create_job("analysis_123", _REPOSITORY)

    with Session(engine) as session:
        assert len(tuple(session.scalars(select(AnalysisOutboxModel)))) == 1


def test_claim_is_leased_and_increments_attempt_count(engine: Engine) -> None:
    outbox = _create_event(engine)
    stale_before = datetime.now(UTC) - timedelta(minutes=1)

    claimed = outbox.claim_pending(claim_token="publisher-a", stale_before=stale_before)
    unavailable = outbox.claim_pending(claim_token="publisher-b", stale_before=stale_before)

    assert len(claimed) == 1
    assert claimed[0].publish_attempts == 1
    assert unavailable == ()


def test_stale_claim_can_be_recovered(engine: Engine) -> None:
    outbox = _create_event(engine)
    now = datetime.now(UTC)
    outbox.claim_pending(claim_token="publisher-a", stale_before=now - timedelta(minutes=1))

    recovered = outbox.claim_pending(
        claim_token="publisher-b",
        stale_before=now + timedelta(minutes=1),
    )

    assert len(recovered) == 1
    assert recovered[0].publish_attempts == 2


def test_mark_published_requires_current_claim(engine: Engine) -> None:
    outbox = _create_event(engine)
    event = outbox.claim_pending(
        claim_token="publisher-a",
        stale_before=datetime.now(UTC) - timedelta(minutes=1),
    )[0]

    with pytest.raises(OutboxClaimConflict):
        outbox.mark_published(event.outbox_id, "publisher-b", "1-0")

    assert outbox.pending_count() == 1


def test_publisher_writes_versioned_message_and_marks_event(engine: Engine) -> None:
    outbox = _create_event(engine)
    redis = FakeRedis(return_bytes=True)

    published = RedisOutboxPublisher(outbox, redis).publish_batch()

    assert published == 1
    assert outbox.pending_count() == 0
    assert redis.published == [
        (
            "repolume:analysis:requests",
            {
                "schema_version": "1.0",
                "event_id": redis.published[0][1]["event_id"],
                "analysis_id": "analysis_123",
                "provider": "github",
                "owner": "octocat",
                "repository": "Hello-World",
                "ref": "main",
            },
        )
    ]
    with Session(engine) as session:
        event = session.scalar(select(AnalysisOutboxModel))
        assert event is not None
        assert event.redis_stream_id == "1710000000000-0"
        assert event.claim_token is None


def test_publish_failure_releases_claim_for_retry(engine: Engine) -> None:
    outbox = _create_event(engine)

    with pytest.raises(OutboxPublishError) as raised:
        RedisOutboxPublisher(outbox, FakeRedis(fail=True)).publish_batch()

    assert "private Redis detail" not in str(raised.value)
    assert outbox.pending_count() == 1
    retried = RedisOutboxPublisher(outbox, FakeRedis()).publish_batch()
    assert retried == 1


def test_empty_batch_does_not_write(engine: Engine) -> None:
    redis = FakeRedis()

    assert RedisOutboxPublisher(AnalysisOutboxStorage(engine), redis).publish_batch() == 0
    assert redis.published == []


@pytest.mark.parametrize("limit", [0, 101])
def test_claim_rejects_unbounded_batch_sizes(engine: Engine, limit: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        AnalysisOutboxStorage(engine).claim_pending(
            claim_token="publisher-a",
            stale_before=datetime.now(UTC),
            limit=limit,
        )


def test_corrupt_stored_event_is_not_published_or_exposed(engine: Engine) -> None:
    outbox = _create_event(engine)
    with Session(engine) as session:
        event = session.scalar(select(AnalysisOutboxModel))
        assert event is not None
        event.payload = {"schema_version": "private malformed value"}
        session.commit()

    with pytest.raises(OutboxPublishError) as raised:
        outbox.claim_pending(
            claim_token="publisher-a",
            stale_before=datetime.now(UTC),
        )

    assert "private malformed value" not in str(raised.value)
    assert outbox.pending_count() == 1


def test_batch_failure_releases_unattempted_events_immediately(engine: Engine) -> None:
    storage = AnalysisStorage(engine)
    storage.create_job("analysis_123", _REPOSITORY)
    storage.create_job("analysis_124", _REPOSITORY)
    outbox = AnalysisOutboxStorage(engine)

    with pytest.raises(OutboxPublishError):
        RedisOutboxPublisher(outbox, FakeRedis(fail_after=1)).publish_batch()

    assert outbox.pending_count() == 1
    assert RedisOutboxPublisher(outbox, FakeRedis()).publish_batch() == 1
