"""ai purpose provider and model preferences

Revision ID: 0022_ai_purpose_preferences
Revises: 0021_seen_job_applied_at
Create Date: 2026-07-03

Per-purpose AI provider/model overrides for cover letters and future agents.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_ai_purpose_preferences"
down_revision: str | None = "0021_seen_job_applied_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("ai_purpose_providers", sa.JSON(), nullable=True))
    op.add_column("user", sa.Column("ai_purpose_models", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "ai_purpose_models")
    op.drop_column("user", "ai_purpose_providers")
