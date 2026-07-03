"""inbox reply draft audit log

Revision ID: 0029_inbox_reply_draft
Revises: 0028_inbox_poll_state
Create Date: 2026-07-03

Stores dry-run recruiter reply drafts for dev inbox automation (Phase 20d).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_inbox_reply_draft"
down_revision: str | None = "0028_inbox_poll_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_reply_draft",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("inbox_classification_id", sa.Integer(), nullable=False),
        sa.Column("seen_job_id", sa.Integer(), nullable=True),
        sa.Column("message_uid", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False, server_default=""),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["inbox_classification_id"], ["inbox_classification.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["seen_job_id"], ["seen_job.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "user_id",
            "inbox_classification_id",
            name="uq_inbox_reply_draft_user_classification",
        ),
    )
    op.create_index("ix_inbox_reply_draft_user_id", "inbox_reply_draft", ["user_id"])
    op.create_index(
        "ix_inbox_reply_draft_inbox_classification_id",
        "inbox_reply_draft",
        ["inbox_classification_id"],
    )
    op.create_index("ix_inbox_reply_draft_seen_job_id", "inbox_reply_draft", ["seen_job_id"])


def downgrade() -> None:
    op.drop_index("ix_inbox_reply_draft_seen_job_id", table_name="inbox_reply_draft")
    op.drop_index(
        "ix_inbox_reply_draft_inbox_classification_id", table_name="inbox_reply_draft"
    )
    op.drop_index("ix_inbox_reply_draft_user_id", table_name="inbox_reply_draft")
    op.drop_table("inbox_reply_draft")
