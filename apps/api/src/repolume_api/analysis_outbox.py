"""Transactional outbox claims and Redis Stream publication."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from sqlalchemy import Engine, func, or_, select, update
from sqlalchemy.orm import sessionmaker

from repolume_api.database_models import AnalysisOutboxModel


class OutboxClaimConflict(RuntimeError):
    """Raised when a publisher no longer owns an outbox event."""


class OutboxPublishError(RuntimeError):
    """Safe publication failure that leaves the event retryable."""


@dataclass(frozen=True, slots=True)
class PendingAnalysisEvent:
    outbox_id: str
    analysis_id: str
    provider: str
    owner: str
    repository: str
    ref: str | None
    publish_attempts: int

    def stream_fields(self) -> dict[str, str]:
        return {
            "schema_version": "1.0",
            "event_id": self.outbox_id,
            "analysis_id": self.analysis_id,
            "provider": self.provider,
            "owner": self.owner,
            "repository": self.repository,
            "ref": self.ref or "",
        }


class RedisStreamWriter(Protocol):
    def xadd(self, name: str, fields: dict[str, str]) -> str | bytes: ...


class AnalysisOutboxStorage:
    """Lease unpublished events without holding a transaction during Redis I/O."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    @staticmethod
    def _event(model: AnalysisOutboxModel) -> PendingAnalysisEvent:
        payload = model.payload
        required = {
            "schema_version",
            "analysis_id",
            "provider",
            "owner",
            "repository",
            "ref",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != required
            or payload.get("schema_version") != "1.0"
            or payload.get("analysis_id") != model.analysis_id
            or payload.get("provider") != "github"
            or not isinstance(payload.get("owner"), str)
            or not payload["owner"]
            or not isinstance(payload.get("repository"), str)
            or not payload["repository"]
            or (payload.get("ref") is not None and not isinstance(payload["ref"], str))
        ):
            raise OutboxPublishError("Stored analysis event is invalid.")
        return PendingAnalysisEvent(
            outbox_id=model.outbox_id,
            analysis_id=payload["analysis_id"],
            provider=payload["provider"],
            owner=payload["owner"],
            repository=payload["repository"],
            ref=payload["ref"],
            publish_attempts=model.publish_attempts,
        )

    def claim_pending(
        self,
        *,
        claim_token: str,
        stale_before: datetime,
        limit: int = 100,
    ) -> tuple[PendingAnalysisEvent, ...]:
        if not claim_token or len(claim_token) > 36:
            raise ValueError("claim_token must contain 1 to 36 characters")
        if not 1 <= limit <= 100:
            raise ValueError("outbox claim limit must be between 1 and 100")

        with self._sessions.begin() as session:
            rows = tuple(
                session.scalars(
                    select(AnalysisOutboxModel)
                    .where(
                        AnalysisOutboxModel.published_at.is_(None),
                        or_(
                            AnalysisOutboxModel.claimed_at.is_(None),
                            AnalysisOutboxModel.claimed_at < stale_before,
                        ),
                    )
                    .order_by(AnalysisOutboxModel.created_at, AnalysisOutboxModel.outbox_id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for row in rows:
                row.claim_token = claim_token
                row.claimed_at = func.now()
                row.publish_attempts += 1
            session.flush()
            return tuple(self._event(row) for row in rows)

    def mark_published(self, outbox_id: str, claim_token: str, stream_id: str) -> None:
        if not stream_id or len(stream_id) > 64:
            raise ValueError("Redis stream ID must contain 1 to 64 characters")
        with self._sessions.begin() as session:
            result = session.execute(
                update(AnalysisOutboxModel)
                .where(
                    AnalysisOutboxModel.outbox_id == outbox_id,
                    AnalysisOutboxModel.claim_token == claim_token,
                    AnalysisOutboxModel.published_at.is_(None),
                )
                .values(
                    published_at=func.now(),
                    redis_stream_id=stream_id,
                    claim_token=None,
                    claimed_at=None,
                )
            )
            if result.rowcount != 1:
                raise OutboxClaimConflict("Outbox publication claim was lost.")

    def release_claim(self, outbox_id: str, claim_token: str) -> None:
        with self._sessions.begin() as session:
            result = session.execute(
                update(AnalysisOutboxModel)
                .where(
                    AnalysisOutboxModel.outbox_id == outbox_id,
                    AnalysisOutboxModel.claim_token == claim_token,
                    AnalysisOutboxModel.published_at.is_(None),
                )
                .values(claim_token=None, claimed_at=None)
            )
            if result.rowcount != 1:
                raise OutboxClaimConflict("Outbox publication claim was lost.")

    def pending_count(self) -> int:
        with self._sessions() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(AnalysisOutboxModel)
                    .where(AnalysisOutboxModel.published_at.is_(None))
                )
                or 0
            )


class RedisOutboxPublisher:
    """Publish claimed outbox events with at-least-once delivery semantics."""

    def __init__(
        self,
        storage: AnalysisOutboxStorage,
        redis: RedisStreamWriter,
        *,
        stream_name: str = "repolume:analysis:requests",
        claim_timeout: timedelta = timedelta(minutes=1),
    ) -> None:
        if not stream_name or len(stream_name) > 128:
            raise ValueError("Redis stream name must contain 1 to 128 characters")
        if claim_timeout <= timedelta(0):
            raise ValueError("outbox claim timeout must be positive")
        self._storage = storage
        self._redis = redis
        self._stream_name = stream_name
        self._claim_timeout = claim_timeout

    def _release_claims(
        self,
        events: tuple[PendingAnalysisEvent, ...],
        claim_token: str,
    ) -> None:
        for event in events:
            try:
                self._storage.release_claim(event.outbox_id, claim_token)
            except OutboxClaimConflict:
                continue

    def publish_batch(self, *, limit: int = 100) -> int:
        claim_token = str(uuid4())
        events = self._storage.claim_pending(
            claim_token=claim_token,
            stale_before=datetime.now(UTC) - self._claim_timeout,
            limit=limit,
        )
        published = 0
        for index, event in enumerate(events):
            try:
                stream_id = self._redis.xadd(self._stream_name, event.stream_fields())
                normalized_id = (
                    stream_id.decode("ascii") if isinstance(stream_id, bytes) else stream_id
                )
                self._storage.mark_published(event.outbox_id, claim_token, normalized_id)
                published += 1
            except OutboxClaimConflict:
                self._release_claims(events[index + 1 :], claim_token)
                raise
            except Exception as exc:
                self._release_claims(events[index:], claim_token)
                raise OutboxPublishError("Analysis event could not be published.") from exc
        return published
