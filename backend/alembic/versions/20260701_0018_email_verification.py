"""add email verification

Revision ID: 0018_email_verification
Revises: 0017_gdpr_data_request_log
Create Date: 2026-07-01

Email verification for new accounts; existing users are grandfathered as verified.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_email_verification"
down_revision: str | None = "0017_gdpr_data_request_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        'UPDATE "user" SET email_verified_at = created_at WHERE email_verified_at IS NULL'
    )

    op.create_table(
        "email_verification_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verification_token_user_id",
        "email_verification_token",
        ["user_id"],
    )
    op.create_index(
        "ix_email_verification_token_token_hash",
        "email_verification_token",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_token_token_hash", table_name="email_verification_token")
    op.drop_index("ix_email_verification_token_user_id", table_name="email_verification_token")
    op.drop_table("email_verification_token")
    op.drop_column("user", "email_verified_at")
