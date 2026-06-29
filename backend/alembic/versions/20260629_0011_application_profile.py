"""application profile (encrypted candidate data)

Revision ID: 0011_application_profile
Revises: 0010_seen_job_summary
Create Date: 2026-06-29

Stores one encrypted candidate profile per user (contact details, resume text,
cover-letter template, per-field answers) as the foundation for auto-apply. The
whole JSON payload is Fernet-encrypted; only `data_ciphertext` is persisted.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_application_profile"
down_revision: str | None = "0010_seen_job_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("data_ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_application_profile_user_id", "application_profile", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_application_profile_user_id", table_name="application_profile")
    op.drop_table("application_profile")
