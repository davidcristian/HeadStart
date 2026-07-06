"""document generation queue

Revision ID: 0040_document_generation
Revises: 0039_user_stripe_billing_event_at
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_document_generation"
down_revision: str | None = "0039_stripe_bill_evt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_generation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("seen_job_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["seen_job_id"], ["seen_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_generation_user_id", "document_generation", ["user_id"])
    op.create_index(
        "ix_document_generation_seen_job_id", "document_generation", ["seen_job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_generation_seen_job_id", table_name="document_generation")
    op.drop_index("ix_document_generation_user_id", table_name="document_generation")
    op.drop_table("document_generation")
