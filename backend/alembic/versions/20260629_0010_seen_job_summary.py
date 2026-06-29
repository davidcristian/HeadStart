"""seen_job match summary

Revision ID: 0010_seen_job_summary
Revises: 0009_seen_job_salary
Create Date: 2026-06-29

Stores the generated "why this matches" blurb on discovered jobs so it can be
shown in the Jobs feed and reused for batched digest notifications.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_seen_job_summary"
down_revision: str | None = "0009_seen_job_salary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("summary", sa.String(length=1000), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("seen_job", "summary")
