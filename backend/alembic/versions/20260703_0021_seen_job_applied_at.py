"""add applied_at on seen_job for apply outcome tracking

Revision ID: 0021_seen_job_applied_at
Revises: 0020_user_summary_preferences
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_seen_job_applied_at"
down_revision: str | None = "0020_user_summary_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seen_job", "applied_at")
