"""add ghost recovery and recruiter reply timestamps on seen_job

Revision ID: 0027_seen_job_ghost_recovery
Revises: 0026_seen_job_ghosted_at
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_seen_job_ghost_recovery"
down_revision: str | None = "0026_seen_job_ghosted_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("ghost_recovered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "seen_job",
        sa.Column("interview_pending_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "seen_job",
        sa.Column("recruiter_rejection_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seen_job", "recruiter_rejection_at")
    op.drop_column("seen_job", "interview_pending_at")
    op.drop_column("seen_job", "ghost_recovered_at")
