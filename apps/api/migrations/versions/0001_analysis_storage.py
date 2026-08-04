"""Create durable analysis job and architecture tables.

Revision ID: 0001_analysis_storage
Revises:
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_analysis_storage"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=39), nullable=False),
        sa.Column("repository", sa.String(length=100), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("requested_ref", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "commit_sha IS NULL OR length(commit_sha) = 40",
            name="ck_analysis_jobs_commit_sha_length",
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR (length(failure_code) BETWEEN 1 AND 100 "
            "AND length(failure_message) BETWEEN 1 AND 500)",
            name="ck_analysis_jobs_failure_fields",
        ),
        sa.CheckConstraint(
            "(status = 'failed' AND failure_code IS NOT NULL "
            "AND failure_message IS NOT NULL) OR "
            "(status <> 'failed' AND failure_code IS NULL "
            "AND failure_message IS NULL)",
            name="ck_analysis_jobs_failure_state",
        ),
        sa.CheckConstraint(
            "(status IN ('completed', 'failed') AND finished_at IS NOT NULL) OR "
            "(status NOT IN ('completed', 'failed') AND finished_at IS NULL)",
            name="ck_analysis_jobs_finished_state",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'cloning', 'analyzing', 'completed', 'failed')",
            name="ck_analysis_jobs_status",
        ),
        sa.PrimaryKeyConstraint("analysis_id"),
    )
    op.create_index(
        "ix_analysis_jobs_status_created_at",
        "analysis_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_table(
        "analysis_architectures",
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(schema_version) > 0",
            name="ck_architectures_schema_version",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analysis_jobs.analysis_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("analysis_id"),
    )


def downgrade() -> None:
    op.drop_table("analysis_architectures")
    op.drop_index("ix_analysis_jobs_status_created_at", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
