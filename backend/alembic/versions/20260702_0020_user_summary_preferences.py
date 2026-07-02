"""user summary provider preferences

Revision ID: 0020_user_summary_preferences
Revises: 0019_migrate_team_to_pro
Create Date: 2026-07-02

Per-user override for SUMMARY_PROVIDER and optional encrypted BYOK API key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_user_summary_preferences"
down_revision: str | None = "0019_migrate_team_to_pro"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("summary_provider", sa.String(length=32), nullable=True))
    op.add_column("user", sa.Column("summary_api_key_ciphertext", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "summary_api_key_ciphertext")
    op.drop_column("user", "summary_provider")
