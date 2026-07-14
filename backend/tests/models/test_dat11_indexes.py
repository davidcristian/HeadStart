"""Regression tests for DAT-11 status-filter indexes on seen_job / delivery_log."""

from __future__ import annotations

from app.models.delivery_log import DeliveryLog
from app.models.seen_job import SeenJob


def test_seen_job_declares_search_id_status_index() -> None:
    """Job feed / applications pipeline filter by search_id + status."""
    by_name = {idx.name: idx for idx in SeenJob.__table__.indexes}
    assert "ix_seen_job_search_id_status" in by_name
    idx = by_name["ix_seen_job_search_id_status"]
    assert [col.name for col in idx.columns] == ["search_id", "status"]


def test_delivery_log_declares_status_index() -> None:
    """Admin stats and failure counts filter delivery_log by status."""
    by_name = {idx.name: idx for idx in DeliveryLog.__table__.indexes}
    assert "ix_delivery_log_status" in by_name
    idx = by_name["ix_delivery_log_status"]
    assert [col.name for col in idx.columns] == ["status"]
