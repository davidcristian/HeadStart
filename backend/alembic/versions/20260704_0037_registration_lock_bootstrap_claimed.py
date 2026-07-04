"""add permanent bootstrap_claimed latch on registration_lock

Revision ID: 0037_reg_lock_claimed
Revises: 0036_application_log_inflight
Create Date: 2026-07-04

Deleting the bootstrap admin SET NULLs bootstrap_user_id, which previously
re-opened claim_bootstrap_admin and auto-promoted the next registrant. A
boolean latch that is never cleared keeps the slot permanently consumed.
Backfill True when an admin already exists or the lock already points at a user.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0037_reg_lock_claimed"
down_revision: str | None = "0036_application_log_inflight"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "registration_lock",
        sa.Column(
            "bootstrap_claimed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Existing deployments that already bootstrapped must not re-open the slot.
    op.execute(
        sa.text(
            """
            UPDATE registration_lock
            SET bootstrap_claimed = TRUE
            WHERE bootstrap_user_id IS NOT NULL
               OR EXISTS (SELECT 1 FROM "user" WHERE is_admin IS TRUE)
            """
        )
    )
    op.alter_column("registration_lock", "bootstrap_claimed", server_default=None)


def downgrade() -> None:
    op.drop_column("registration_lock", "bootstrap_claimed")
