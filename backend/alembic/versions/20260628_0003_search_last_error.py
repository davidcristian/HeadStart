"""add last_error to search

Revision ID: 0003_search_last_error
Revises: 0002_accounts
Create Date: 2026-06-28

Stores the most recent scrape failure message on a search for UI health display.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_search_last_error"
down_revision: str | None = "0002_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("search", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("search", "last_error")
