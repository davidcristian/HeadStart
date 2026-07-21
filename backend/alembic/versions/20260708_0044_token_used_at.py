"""add used_at to reset and verify tokens

Revision ID: 0044_token_used_at
Revises: 0043_seen_job_norm_url
Create Date: 2026-07-08

Single-use for password-reset and email-verification tokens previously relied
only on a post-success delete. Persist used_at so claim can mark a
token consumed atomically before any later path that may raise or roll back.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_token_used_at"
down_revision: str | None = "0043_seen_job_norm_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "password_reset_token",
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "email_verification_token",
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_verification_token", "used_at")
    op.drop_column("password_reset_token", "used_at")
