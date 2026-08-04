"""Add transactional analysis request outbox.

Revision ID: 0002_analysis_outbox
Revises: 0001_analysis_storage
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_analysis_outbox"
down_revision: str | None = "0001_analysis_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_outbox_events",
        sa.Column("outbox_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token", sa.String(length=36), nullable=True),
        sa.Column("publish_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redis_stream_id", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "event_type = 'analysis_requested'",
            name="ck_analysis_outbox_event_type",
        ),
        sa.CheckConstraint(
            "publish_attempts >= 0",
            name="ck_analysis_outbox_publish_attempts",
        ),
        sa.CheckConstraint(
            "(published_at IS NULL AND redis_stream_id IS NULL) OR "
            "(published_at IS NOT NULL AND redis_stream_id IS NOT NULL)",
            name="ck_analysis_outbox_published_state",
        ),
        sa.CheckConstraint(
            "(claimed_at IS NULL AND claim_token IS NULL) OR "
            "(claimed_at IS NOT NULL AND claim_token IS NOT NULL)",
            name="ck_analysis_outbox_claim_state",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analysis_jobs.analysis_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("outbox_id"),
        sa.UniqueConstraint(
            "analysis_id",
            "event_type",
            name="uq_analysis_outbox_job_event",
        ),
    )
    op.create_index(
        "ix_analysis_outbox_pending",
        "analysis_outbox_events",
        ["published_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_outbox_pending", table_name="analysis_outbox_events")
    op.drop_table("analysis_outbox_events")
