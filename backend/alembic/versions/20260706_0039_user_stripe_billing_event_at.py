"""add user.stripe_billing_event_at for webhook ordering

Revision ID: 0039_stripe_bill_evt
Revises: 0038_redact_data_req
Create Date: 2026-07-06

Stores the Stripe event ``created`` unix timestamp of the last applied
subscription lifecycle webhook so stale/out-of-order updated/deleted events
cannot regress plan state (BIL-02 / BIL-03).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039_stripe_bill_evt"
down_revision: str | None = "0038_redact_data_req"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("stripe_billing_event_at", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "stripe_billing_event_at")
