"""inbox poll state (last processed mailbox UID per user)

Revision ID: 0028_inbox_poll_state
Revises: 0027_seen_job_ghost_recovery
Create Date: 2026-07-03

Tracks the IMAP UID cursor for beat-driven inbox orchestration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_inbox_poll_state"
down_revision: str | None = "0027_seen_job_ghost_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_poll_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_polled_uid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_inbox_poll_state_user_id", "inbox_poll_state", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_inbox_poll_state_user_id", table_name="inbox_poll_state")
    op.drop_table("inbox_poll_state")
