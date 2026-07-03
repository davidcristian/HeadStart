"""inbox pending reply delay queue

Revision ID: 0030_inbox_pending_reply
Revises: 0029_inbox_reply_draft
Create Date: 2026-07-03

Stores human-like send delays before auto-reply SMTP delivery (Phase 20d).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_inbox_pending_reply"
down_revision: str | None = "0029_inbox_reply_draft"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_pending_reply",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("inbox_reply_draft_id", sa.Integer(), nullable=False),
        sa.Column("send_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["inbox_reply_draft_id"], ["inbox_reply_draft.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "inbox_reply_draft_id",
            name="uq_inbox_pending_reply_draft",
        ),
    )
    op.create_index("ix_inbox_pending_reply_user_id", "inbox_pending_reply", ["user_id"])
    op.create_index(
        "ix_inbox_pending_reply_inbox_reply_draft_id",
        "inbox_pending_reply",
        ["inbox_reply_draft_id"],
    )
    op.create_index(
        "ix_inbox_pending_reply_send_after",
        "inbox_pending_reply",
        ["send_after"],
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_pending_reply_send_after", table_name="inbox_pending_reply")
    op.drop_index(
        "ix_inbox_pending_reply_inbox_reply_draft_id", table_name="inbox_pending_reply"
    )
    op.drop_index("ix_inbox_pending_reply_user_id", table_name="inbox_pending_reply")
    op.drop_table("inbox_pending_reply")
