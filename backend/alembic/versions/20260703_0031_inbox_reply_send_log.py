"""inbox reply send audit log

Revision ID: 0031_inbox_reply_send_log
Revises: 0030_inbox_pending_reply
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_inbox_reply_send_log"
down_revision: str | None = "0030_inbox_pending_reply"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_reply_send_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("inbox_reply_draft_id", sa.Integer(), nullable=False),
        sa.Column("inbox_pending_reply_id", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("body_excerpt", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inbox_pending_reply_id"], ["inbox_pending_reply.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["inbox_reply_draft_id"], ["inbox_reply_draft.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inbox_reply_send_log_user_id", "inbox_reply_send_log", ["user_id"])
    op.create_index(
        "ix_inbox_reply_send_log_inbox_reply_draft_id",
        "inbox_reply_send_log",
        ["inbox_reply_draft_id"],
    )
    op.create_index(
        "ix_inbox_reply_send_log_inbox_pending_reply_id",
        "inbox_reply_send_log",
        ["inbox_pending_reply_id"],
    )
    op.create_index(
        "ix_inbox_reply_send_log_created_at",
        "inbox_reply_send_log",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_reply_send_log_created_at", table_name="inbox_reply_send_log")
    op.drop_index(
        "ix_inbox_reply_send_log_inbox_pending_reply_id", table_name="inbox_reply_send_log"
    )
    op.drop_index(
        "ix_inbox_reply_send_log_inbox_reply_draft_id", table_name="inbox_reply_send_log"
    )
    op.drop_index("ix_inbox_reply_send_log_user_id", table_name="inbox_reply_send_log")
    op.drop_table("inbox_reply_send_log")
