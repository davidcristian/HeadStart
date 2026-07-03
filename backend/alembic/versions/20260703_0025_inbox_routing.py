"""inbox folder routing config and classification routing audit

Revision ID: 0025_inbox_routing
Revises: 0024_inbox_classification
Create Date: 2026-07-03

Adds per-user label→folder routing settings and routing outcome columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_inbox_routing"
down_revision: str | None = "0024_inbox_classification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mailbox_credential", sa.Column("routing_config", sa.JSON(), nullable=True))
    op.add_column(
        "inbox_classification",
        sa.Column("routed_to", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "inbox_classification",
        sa.Column("routing_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "inbox_classification",
        sa.Column("routing_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inbox_classification", "routing_error")
    op.drop_column("inbox_classification", "routing_status")
    op.drop_column("inbox_classification", "routed_to")
    op.drop_column("mailbox_credential", "routing_config")
