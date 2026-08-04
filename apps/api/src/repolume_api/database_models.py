"""SQLAlchemy models for durable analysis jobs and architecture artifacts."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ANALYSIS_STATUSES = ("queued", "cloning", "analyzing", "completed", "failed")
ArchitecturePayload = dict[str, Any]


class Base(DeclarativeBase):
    """Declarative metadata root used by models and Alembic."""


class AnalysisJobModel(Base):
    """Durable lifecycle and repository identity for one analysis attempt."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'cloning', 'analyzing', 'completed', 'failed')",
            name="ck_analysis_jobs_status",
        ),
        CheckConstraint(
            "(status = 'failed' AND failure_code IS NOT NULL "
            "AND failure_message IS NOT NULL) OR "
            "(status <> 'failed' AND failure_code IS NULL "
            "AND failure_message IS NULL)",
            name="ck_analysis_jobs_failure_state",
        ),
        CheckConstraint(
            "commit_sha IS NULL OR length(commit_sha) = 40",
            name="ck_analysis_jobs_commit_sha_length",
        ),
        CheckConstraint(
            "failure_code IS NULL OR (length(failure_code) BETWEEN 1 AND 100 "
            "AND length(failure_message) BETWEEN 1 AND 500)",
            name="ck_analysis_jobs_failure_fields",
        ),
        CheckConstraint(
            "(status IN ('completed', 'failed') AND finished_at IS NOT NULL) OR "
            "(status NOT IN ('completed', 'failed') AND finished_at IS NULL)",
            name="ck_analysis_jobs_finished_state",
        ),
        Index("ix_analysis_jobs_status_created_at", "status", "created_at"),
    )

    analysis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    owner: Mapped[str] = mapped_column(String(39), nullable=False)
    repository: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    requested_ref: Mapped[str | None] = mapped_column(String(255))
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    architecture: Mapped["AnalysisArchitectureModel | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class AnalysisArchitectureModel(Base):
    """One versioned architecture payload owned by a completed analysis."""

    __tablename__ = "analysis_architectures"
    __table_args__ = (
        CheckConstraint("length(schema_version) > 0", name="ck_architectures_schema_version"),
    )

    analysis_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("analysis_jobs.analysis_id", ondelete="CASCADE"),
        primary_key=True,
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[ArchitecturePayload] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    job: Mapped[AnalysisJobModel] = relationship(back_populates="architecture")
