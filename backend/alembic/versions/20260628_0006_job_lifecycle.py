"""job lifecycle: status on seen_job

Revision ID: 0006_job_lifecycle
Revises: 0005_digest_mode
Create Date: 2026-06-28

Adds a triage status to seen_job rows (new/seen/applied/archived/closed).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_job_lifecycle"
down_revision: str | None = "0005_digest_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
    )


def downgrade() -> None:
    op.drop_column("seen_job", "status")
