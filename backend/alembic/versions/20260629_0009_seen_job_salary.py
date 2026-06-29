"""seen_job salary display

Revision ID: 0009_seen_job_salary
Revises: 0008_registration_lock
Create Date: 2026-06-29

Stores a formatted compensation summary on discovered jobs when available.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_seen_job_salary"
down_revision: str | None = "0008_registration_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("salary", sa.String(length=200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("seen_job", "salary")
