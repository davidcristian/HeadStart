"""persist normalized_url for cross-search dedup

Revision ID: 0043_seen_job_norm_url
Revises: 0042_seen_job_app_log_idx
Create Date: 2026-07-06

Cross-search dedup used to SELECT every seen_job.url for a user and normalize
in Python on each scrape. Persist the canonical URL at insert time and
index it so the batch intersect can run in SQL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_seen_job_norm_url"
down_revision: str | None = "0042_seen_job_app_log_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_seen_job_normalized_url"


def upgrade() -> None:
    op.add_column(
        "seen_job",
        sa.Column("normalized_url", sa.String(length=2000), nullable=False, server_default=""),
    )
    # Backfill from stored urls with the same Python normalizer the pipeline uses.
    from app.scrapers.url import normalize_job_url

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, url FROM seen_job WHERE url != ''")).fetchall()
    for row_id, url in rows:
        normalized = normalize_job_url(url)
        if normalized:
            bind.execute(
                sa.text("UPDATE seen_job SET normalized_url = :n WHERE id = :id"),
                {"n": normalized, "id": row_id},
            )
    op.create_index(_INDEX, "seen_job", ["normalized_url"])


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="seen_job")
    op.drop_column("seen_job", "normalized_url")
