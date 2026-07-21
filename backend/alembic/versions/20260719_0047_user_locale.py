"""add user.locale for notification/auth copy

Revision ID: 0047_user_locale
Revises: 0046_status_filter_idx
Create Date: 2026-07-19

Per-user preferred locale for digest/notification and auth email catalogs.
Null inherits Settings.default_locale.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_user_locale"
down_revision: str | None = "0046_status_filter_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("locale", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "locale")
