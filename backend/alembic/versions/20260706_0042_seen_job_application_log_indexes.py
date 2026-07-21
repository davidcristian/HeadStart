"""indexes for ghost detection and live-apply lookups

Revision ID: 0042_seen_job_app_log_idx
Revises: 0041_search_run
Create Date: 2026-07-06

Ghost detection filters seen_job by status/applied_at where ghosted_at IS NULL
on every beat tick; the applications pipeline distinct subquery filters
application_log by dry_run. Neither path had a supporting index.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_seen_job_app_log_idx"
down_revision: str | None = "0041_search_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEEN_JOB_INDEX = "ix_seen_job_status_applied_at_unghosted"
_APP_LOG_INDEX = "ix_application_log_dry_run_seen_job_id"


def upgrade() -> None:
    op.create_index(
        _SEEN_JOB_INDEX,
        "seen_job",
        ["status", "applied_at"],
        postgresql_where=sa.text("ghosted_at IS NULL"),
        sqlite_where=sa.text("ghosted_at IS NULL"),
    )
    op.create_index(
        _APP_LOG_INDEX,
        "application_log",
        ["dry_run", "seen_job_id"],
    )


def downgrade() -> None:
    op.drop_index(_APP_LOG_INDEX, table_name="application_log")
    op.drop_index(_SEEN_JOB_INDEX, table_name="seen_job")
