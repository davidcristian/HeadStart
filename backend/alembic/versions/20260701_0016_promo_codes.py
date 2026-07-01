"""add promo codes and redemptions

Revision ID: 0016_promo_codes
Revises: 0015_auto_apply_consent
Create Date: 2026-07-01

Promo codes for checkout discounts, extended trials, and plan upgrades.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_promo_codes"
down_revision: str | None = "0015_auto_apply_consent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "promo_code",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("promo_type", sa.String(length=32), nullable=False),
        sa.Column("value_int", sa.Integer(), nullable=False),
        sa.Column("plan_target", sa.String(length=20), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redemption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("one_per_user", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("eligible_plans", sa.JSON(), nullable=True),
        sa.Column("stripe_coupon_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_promotion_code_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promo_code_code", "promo_code", ["code"], unique=True)

    op.create_table(
        "promo_redemption",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("promo_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_code.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promo_redemption_promo_code_id", "promo_redemption", ["promo_code_id"])
    op.create_index("ix_promo_redemption_user_id", "promo_redemption", ["user_id"])

    op.create_table(
        "promo_validation_attempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_entered", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_promo_validation_attempt_user_id", "promo_validation_attempt", ["user_id"]
    )
    op.create_index(
        "ix_promo_validation_attempt_created_at",
        "promo_validation_attempt",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_promo_validation_attempt_created_at", table_name="promo_validation_attempt")
    op.drop_index("ix_promo_validation_attempt_user_id", table_name="promo_validation_attempt")
    op.drop_table("promo_validation_attempt")
    op.drop_index("ix_promo_redemption_user_id", table_name="promo_redemption")
    op.drop_index("ix_promo_redemption_promo_code_id", table_name="promo_redemption")
    op.drop_table("promo_redemption")
    op.drop_index("ix_promo_code_code", table_name="promo_code")
    op.drop_table("promo_code")
