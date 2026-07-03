"""Tests for the scheduler's atomic claim of due searches (no double-enqueue)."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.repositories.searches import SearchRepository
from tests.worker.pipeline_helpers import aware, make_search


def test_claim_due_advances_next_run_and_prevents_double_enqueue(db_session: Session) -> None:
    now = utcnow()
    search = make_search(db_session, interval=300, next_run_at=now - timedelta(seconds=5))
    repo = SearchRepository(db_session)

    assert repo.claim_due(now) == [search.id]
    db_session.refresh(search)
    assert aware(search.next_run_at) > now  # the claim advanced the schedule

    # A tick at the same instant (slow scrape / overlap) must not re-enqueue it.
    assert repo.claim_due(now) == []


def test_claim_due_skips_disabled_and_future_searches(db_session: Session) -> None:
    now = utcnow()
    make_search(db_session, interval=300, next_run_at=now + timedelta(seconds=300))
    disabled = make_search(db_session, next_run_at=now - timedelta(seconds=5))
    disabled.enabled = False
    db_session.flush()

    assert SearchRepository(db_session).claim_due(now) == []
