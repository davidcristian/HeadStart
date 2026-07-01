"""add onboarding_completed_at to user

Revision ID: 0012_onboarding_completed
Revises: 0011_application_profile
Create Date: 2026-07-01

Tracks whether the first-run onboarding wizard has been completed.
Existing users with at least one search are backfilled as already onboarded.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_onboarding_completed"
down_revision: str | None = "0011_application_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Users who already created a search have effectively finished setup.
    op.execute(
        """
        UPDATE "user"
        SET onboarding_completed_at = created_at
        WHERE id IN (SELECT DISTINCT user_id FROM search)
        """
    )


def downgrade() -> None:
    op.drop_column("user", "onboarding_completed_at")
