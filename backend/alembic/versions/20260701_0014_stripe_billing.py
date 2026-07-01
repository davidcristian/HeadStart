"""add stripe billing columns to user

Revision ID: 0014_stripe_billing
Revises: 0013_user_plan
Create Date: 2026-07-01

Stores Stripe customer/subscription IDs and subscription status for webhooks.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_stripe_billing"
down_revision: str | None = "0013_user_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("subscription_status", sa.String(length=50), nullable=True))
    op.create_index("ix_user_stripe_customer_id", "user", ["stripe_customer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_stripe_customer_id", table_name="user")
    op.drop_column("user", "subscription_status")
    op.drop_column("user", "stripe_subscription_id")
    op.drop_column("user", "stripe_customer_id")
