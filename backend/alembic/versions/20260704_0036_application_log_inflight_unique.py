"""partial unique index on in-flight application_log rows

Revision ID: 0036_application_log_inflight_unique
Revises: 0035_user_token_version
Create Date: 2026-07-04

enqueue_apply was a read-then-write with no DB guard, so a double-click or
concurrent API retry could insert two queued rows and dispatch two live
apply_to_job_task workers for the same job. Enforce at most one in-flight live
apply per seen_job at the database level; the service catches IntegrityError and
treats the duplicate as already in progress. De-dupe any pre-existing in-flight
rows first (keep the earliest) so the index can be created.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0036_application_log_inflight_unique"
down_revision: str | None = "0035_user_token_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "uq_application_log_inflight_job"
_WHERE = "status IN ('queued', 'processing') AND dry_run = 0"


def upgrade() -> None:
    op.execute(
        f"""
        DELETE FROM application_log
        WHERE dry_run = 0
          AND status IN ('queued', 'processing')
          AND id NOT IN (
              SELECT MIN(id)
              FROM application_log
              WHERE dry_run = 0
                AND status IN ('queued', 'processing')
              GROUP BY seen_job_id
          )
        """
    )
    op.create_index(
        _INDEX,
        "application_log",
        ["seen_job_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'processing') AND dry_run IS FALSE"
        ),
        sqlite_where=sa.text(_WHERE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="application_log")
