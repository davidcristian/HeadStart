"""Regression: DAT-11 status-filter indexes land in Alembic revision 0046."""

from __future__ import annotations

from pathlib import Path

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"
_MIGRATION = _VERSIONS / "20260714_0046_seen_job_delivery_log_status_indexes.py"


def test_status_filter_migration_creates_both_indexes() -> None:
    """Upgrade must add search_id+status on seen_job and status on delivery_log."""
    text = _MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "0046_status_filter_idx"' in text
    assert 'down_revision: str | None = "0045_reply_send_defaults"' in text
    assert 'op.create_index(_SEEN_JOB_INDEX, "seen_job", ["search_id", "status"])' in text
    assert 'op.create_index(_DELIVERY_LOG_INDEX, "delivery_log", ["status"])' in text
    assert 'op.drop_index(_DELIVERY_LOG_INDEX, table_name="delivery_log")' in text
    assert 'op.drop_index(_SEEN_JOB_INDEX, table_name="seen_job")' in text
