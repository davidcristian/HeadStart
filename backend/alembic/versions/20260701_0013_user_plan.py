"""add plan column to user

Revision ID: 0013_user_plan
Revises: 0012_onboarding_completed
Create Date: 2026-07-01

Tracks the subscription tier for plan limits enforcement.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_user_plan"
down_revision: str | None = "0012_onboarding_completed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"),
    )


def downgrade() -> None:
    op.drop_column("user", "plan")
