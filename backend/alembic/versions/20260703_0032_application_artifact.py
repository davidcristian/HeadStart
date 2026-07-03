"""application artifact store

Revision ID: 0032_application_artifact
Revises: 0031_inbox_reply_send_log
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_application_artifact"
down_revision: str | None = "0031_inbox_reply_send_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data_ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "content_sha256", name="uq_application_artifact_user_hash"),
    )
    op.create_index("ix_application_artifact_user_id", "application_artifact", ["user_id"])
    op.add_column(
        "application_log",
        sa.Column("tailored_resume_artifact_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_application_log_tailored_resume_artifact_id",
        "application_log",
        "application_artifact",
        ["tailored_resume_artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_application_log_tailored_resume_artifact_id",
        "application_log",
        ["tailored_resume_artifact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_log_tailored_resume_artifact_id", table_name="application_log")
    op.drop_constraint(
        "fk_application_log_tailored_resume_artifact_id", "application_log", type_="foreignkey"
    )
    op.drop_column("application_log", "tailored_resume_artifact_id")
    op.drop_index("ix_application_artifact_user_id", table_name="application_artifact")
    op.drop_table("application_artifact")
