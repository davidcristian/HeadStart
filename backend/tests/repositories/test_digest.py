"""PendingDigestRepository regressions for bulk clear and batch add."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pending_digest import PendingDigest
from app.models.seen_job import SeenJob
from app.repositories.digest import PendingDigestRepository
from tests.worker.pipeline_helpers import make_search


def _seen_job(session: Session, search_id: int, external_id: str) -> SeenJob:
    job = SeenJob(
        search_id=search_id,
        external_id=external_id,
        hash=f"hash-{external_id}",
        title=f"Job {external_id}",
        company="Acme",
        location="Remote",
        url=f"https://example.test/{external_id}",
        status="new",
    )
    session.add(job)
    session.flush()
    return job


def test_add_many_flushes_once_for_batch(db_session: Session) -> None:
    """Queueing N jobs issues one flush, not one per row."""
    search = make_search(db_session)
    jobs = [_seen_job(db_session, search.id, eid) for eid in ("a1", "a2", "a3")]
    repo = PendingDigestRepository(db_session)
    flush_calls = 0
    original_flush = db_session.flush

    def counting_flush(*args: object, **kwargs: object) -> None:
        nonlocal flush_calls
        flush_calls += 1
        original_flush(*args, **kwargs)

    db_session.flush = counting_flush  # type: ignore[method-assign]
    rows = repo.add_many(search.id, [job.id for job in jobs])
    assert len(rows) == 3
    assert flush_calls == 1
    assert len(repo.list_for_search(search.id)) == 3


def test_add_many_empty_is_noop(db_session: Session) -> None:
    search = make_search(db_session)
    assert PendingDigestRepository(db_session).add_many(search.id, []) == []
    assert db_session.scalars(select(PendingDigest)).all() == []


def test_add_delegates_to_add_many(db_session: Session) -> None:
    search = make_search(db_session)
    job = _seen_job(db_session, search.id, "solo")
    row = PendingDigestRepository(db_session).add(search.id, job.id)
    assert row.seen_job_id == job.id
    assert len(PendingDigestRepository(db_session).list_for_search(search.id)) == 1


def test_delete_for_search_bulk_clears_only_that_search(db_session: Session) -> None:
    """Flush clears one search's queue in a single DELETE, leaving others intact."""
    search_a = make_search(db_session)
    search_b = make_search(db_session)
    jobs_a = [_seen_job(db_session, search_a.id, eid) for eid in ("a1", "a2", "a3")]
    job_b = _seen_job(db_session, search_b.id, "b1")
    repo = PendingDigestRepository(db_session)
    for job in jobs_a:
        repo.add(search_a.id, job.id)
    repo.add(search_b.id, job_b.id)
    db_session.flush()

    assert len(repo.list_for_search(search_a.id)) == 3
    assert len(repo.list_for_search(search_b.id)) == 1

    repo.delete_for_search(search_a.id)
    db_session.flush()
    db_session.expire_all()

    remaining = list(db_session.scalars(select(PendingDigest)))
    assert [row.search_id for row in remaining] == [search_b.id]
    assert repo.list_for_search(search_a.id) == []
    assert len(repo.list_for_search(search_b.id)) == 1


def test_delete_for_search_is_noop_when_empty(db_session: Session) -> None:
    search = make_search(db_session)
    PendingDigestRepository(db_session).delete_for_search(search.id)
    db_session.flush()
    assert db_session.scalars(select(PendingDigest)).all() == []
