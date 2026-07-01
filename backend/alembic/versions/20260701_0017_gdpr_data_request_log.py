"""add GDPR data request audit log

Revision ID: 0017_gdpr_data_request_log
Revises: 0016_promo_codes
Create Date: 2026-07-01

Audit trail for account data exports and deletions.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_gdpr_data_request_log"
down_revision: str | None = "0016_promo_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_request_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(length=320), nullable=False),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_request_log_user_id", "data_request_log", ["user_id"])
    op.create_index("ix_data_request_log_created_at", "data_request_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_request_log_created_at", table_name="data_request_log")
    op.drop_index("ix_data_request_log_user_id", table_name="data_request_log")
    op.drop_table("data_request_log")
