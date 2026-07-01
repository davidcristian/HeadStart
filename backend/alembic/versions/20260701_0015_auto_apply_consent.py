"""add auto_apply_enabled on source and application_log audit table

Revision ID: 0015_auto_apply_consent
Revises: 0014_stripe_billing
Create Date: 2026-07-01

Per-source opt-in for live auto-apply and an audit log of apply attempts.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_auto_apply_consent"
down_revision: str | None = "0014_stripe_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source",
        sa.Column("auto_apply_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "application_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seen_job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("external_application_id", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seen_job_id"], ["seen_job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_log_seen_job_id", "application_log", ["seen_job_id"])


def downgrade() -> None:
    op.drop_index("ix_application_log_seen_job_id", table_name="application_log")
    op.drop_table("application_log")
    op.drop_column("source", "auto_apply_enabled")
