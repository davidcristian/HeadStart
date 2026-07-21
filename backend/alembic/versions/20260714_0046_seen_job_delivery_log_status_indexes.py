"""indexes for status-filtered seen_job and delivery_log reads

Revision ID: 0046_status_filter_idx
Revises: 0045_reply_send_defaults
Create Date: 2026-07-14

Job feed and applications pipeline filter seen_job by search_id + status;
admin stats and search-status count delivery_log by status. The existing
partial ghost index does not cover those callers.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0046_status_filter_idx"
down_revision: str | None = "0045_reply_send_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEEN_JOB_INDEX = "ix_seen_job_search_id_status"
_DELIVERY_LOG_INDEX = "ix_delivery_log_status"


def upgrade() -> None:
    op.create_index(_SEEN_JOB_INDEX, "seen_job", ["search_id", "status"])
    op.create_index(_DELIVERY_LOG_INDEX, "delivery_log", ["status"])


def downgrade() -> None:
    op.drop_index(_DELIVERY_LOG_INDEX, table_name="delivery_log")
    op.drop_index(_SEEN_JOB_INDEX, table_name="seen_job")
