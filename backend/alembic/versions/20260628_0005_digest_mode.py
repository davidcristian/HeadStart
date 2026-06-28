"""digest mode: search settings and pending_digest queue

Revision ID: 0005_digest_mode
Revises: 0004_password_reset
Create Date: 2026-06-28

Adds per-search digest notification settings and a queue table for jobs waiting
to be batched into a single notification.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_digest_mode"
down_revision: str | None = "0004_password_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "search",
        sa.Column("notification_mode", sa.String(length=20), nullable=False, server_default="immediate"),
    )
    op.add_column(
        "search",
        sa.Column("digest_interval_seconds", sa.Integer(), nullable=False, server_default="3600"),
    )
    op.add_column("search", sa.Column("last_digest_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "pending_digest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("search_id", sa.Integer(), nullable=False),
        sa.Column("seen_job_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["search_id"], ["search.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seen_job_id"], ["seen_job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seen_job_id", name="uq_pending_digest_seen_job"),
    )
    op.create_index(op.f("ix_pending_digest_search_id"), "pending_digest", ["search_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_digest_search_id"), table_name="pending_digest")
    op.drop_table("pending_digest")
    op.drop_column("search", "last_digest_at")
    op.drop_column("search", "digest_interval_seconds")
    op.drop_column("search", "notification_mode")
