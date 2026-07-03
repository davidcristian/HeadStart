"""add ghosted_at on seen_job for inbox ghost detection

Revision ID: 0026_seen_job_ghosted_at
Revises: 0025_inbox_routing
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_seen_job_ghosted_at"
down_revision: str | None = "0025_inbox_routing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("ghosted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seen_job", "ghosted_at")
