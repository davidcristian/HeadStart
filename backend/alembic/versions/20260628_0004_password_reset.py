"""add password_reset_token table

Revision ID: 0004_password_reset
Revises: 0003_search_last_error
Create Date: 2026-06-28

Stores single-use, time-limited tokens for email-based password reset.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_password_reset"
down_revision: str | None = "0003_search_last_error"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_password_reset_token_user_id", "password_reset_token", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_token_token_hash", "password_reset_token", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_token_token_hash", table_name="password_reset_token")
    op.drop_index("ix_password_reset_token_user_id", table_name="password_reset_token")
    op.drop_table("password_reset_token")
