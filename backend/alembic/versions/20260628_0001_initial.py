"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28

Creates the five core tables: source, notification_target, search, seen_job,
delivery_log.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("adapter_key", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("default_config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_adapter_key", "source", ["adapter_key"])

    op.create_table(
        "notification_target",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_target_type", "notification_target", ["type"])

    op.create_table(
        "search",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("query_url", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["notification_target.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_search_source_id", "search", ["source_id"])
    op.create_index("ix_search_next_run_at", "search", ["next_run_at"])

    op.create_table(
        "seen_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("company", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["search_id"], ["search.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("search_id", "external_id", name="uq_seen_job_search_external"),
    )
    op.create_index("ix_seen_job_search_id", "seen_job", ["search_id"])

    op.create_table(
        "delivery_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seen_job_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seen_job_id"], ["seen_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["notification_target.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_delivery_log_seen_job_id", "delivery_log", ["seen_job_id"])


def downgrade() -> None:
    op.drop_table("delivery_log")
    op.drop_table("seen_job")
    op.drop_table("search")
    op.drop_table("notification_target")
    op.drop_table("source")
