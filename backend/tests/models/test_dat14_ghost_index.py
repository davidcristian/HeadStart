"""DAT-14: ghost-detection claim path is covered by the unghosted status/applied_at index.

DAT-03 shipped ``ix_seen_job_status_applied_at_unghosted`` for the same root cause;
this regression locks the scheduled claim predicate to that index so a future
index drop cannot silently reintroduce full-table sweeps on every beat tick.
"""

from __future__ import annotations

import inspect

from sqlalchemy import Index

from app.models.seen_job import SeenJob
from app.repositories.ghost_detection import GhostDetectionRepository


def test_unghosted_index_matches_ghost_claim_predicate() -> None:
    """Partial (status, applied_at) WHERE ghosted_at IS NULL covers claim filters."""
    by_name = {idx.name: idx for idx in SeenJob.__table__.indexes}
    assert "ix_seen_job_status_applied_at_unghosted" in by_name
    idx = by_name["ix_seen_job_status_applied_at_unghosted"]
    assert isinstance(idx, Index)
    assert [col.name for col in idx.columns] == ["status", "applied_at"]
    dialect_opts = idx.dialect_options
    assert dialect_opts["postgresql"]["where"].text == "ghosted_at IS NULL"
    assert dialect_opts["sqlite"]["where"].text == "ghosted_at IS NULL"


def test_claim_stale_applications_filters_match_unghosted_index() -> None:
    """Claim WHERE clauses must stay aligned with the partial index columns."""
    source = inspect.getsource(GhostDetectionRepository.claim_stale_applications)
    assert 'SeenJob.status == "applied"' in source
    assert "SeenJob.applied_at.is_not(None)" in source
    assert "SeenJob.applied_at <= cutoff" in source
    assert "SeenJob.ghosted_at.is_(None)" in source
