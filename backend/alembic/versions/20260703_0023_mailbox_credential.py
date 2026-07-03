"""mailbox credential (encrypted IMAP/SMTP settings)

Revision ID: 0023_mailbox_credential
Revises: 0022_ai_purpose_preferences
Create Date: 2026-07-03

Stores one encrypted mailbox credential per user for dev-only inbox automation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_mailbox_credential"
down_revision: str | None = "0022_ai_purpose_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mailbox_credential",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_mailbox_credential_user_id", "mailbox_credential", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_mailbox_credential_user_id", table_name="mailbox_credential")
    op.drop_table("mailbox_credential")
