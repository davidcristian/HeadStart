"""inbox classification audit log

Revision ID: 0024_inbox_classification
Revises: 0023_mailbox_credential
Create Date: 2026-07-03

Stores persisted inbound email classification results for dev inbox automation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_inbox_classification"
down_revision: str | None = "0023_mailbox_credential"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_classification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("seen_job_id", sa.Integer(), nullable=True),
        sa.Column("message_uid", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=True),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("subject", sa.String(length=998), nullable=False, server_default=""),
        sa.Column("from_addr", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seen_job_id"], ["seen_job.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "message_uid", name="uq_inbox_class_user_uid"),
    )
    op.create_index("ix_inbox_classification_user_id", "inbox_classification", ["user_id"])
    op.create_index(
        "ix_inbox_classification_seen_job_id", "inbox_classification", ["seen_job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_classification_seen_job_id", table_name="inbox_classification")
    op.drop_index("ix_inbox_classification_user_id", table_name="inbox_classification")
    op.drop_table("inbox_classification")
