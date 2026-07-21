"""Regression tests for supporting indexes on seen_job / application_log."""

from __future__ import annotations

from sqlalchemy import Index

from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob


def test_seen_job_declares_unghosted_status_applied_at_index() -> None:
    """Ghost-detection filters need a partial (status, applied_at) index."""
    index = SeenJob.__table__.indexes
    by_name = {idx.name: idx for idx in index}
    assert "ix_seen_job_status_applied_at_unghosted" in by_name
    idx = by_name["ix_seen_job_status_applied_at_unghosted"]
    assert isinstance(idx, Index)
    assert [col.name for col in idx.columns] == ["status", "applied_at"]
    dialect_opts = idx.dialect_options
    assert dialect_opts["postgresql"]["where"].text == "ghosted_at IS NULL"
    assert dialect_opts["sqlite"]["where"].text == "ghosted_at IS NULL"


def test_application_log_declares_dry_run_seen_job_index() -> None:
    """Applications pipeline distinct subquery filters dry_run + seen_job_id."""
    by_name = {idx.name: idx for idx in ApplicationLog.__table__.indexes}
    assert "ix_application_log_dry_run_seen_job_id" in by_name
    idx = by_name["ix_application_log_dry_run_seen_job_id"]
    assert [col.name for col in idx.columns] == ["dry_run", "seen_job_id"]
