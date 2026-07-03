"""add token_version to user

Revision ID: 0035_user_token_version
Revises: 0034_promo_redemption_unique
Create Date: 2026-07-03

Tracks access/refresh token rotation so credential changes (password reset) can
revoke previously issued sessions. Mirrors feed_token_version.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0035_user_token_version"
down_revision: str | None = "0034_promo_redemption_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("user", "token_version", server_default=None)


def downgrade() -> None:
    op.drop_column("user", "token_version")
