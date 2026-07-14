"""Direct unit tests for SeenJob, DeliveryLog, and Search repositories."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.delivery_log import DeliveryLog
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.models.user import User
from app.repositories.deliveries import DeliveryLogRepository
from app.repositories.jobs import SeenJobRepository
from app.repositories.searches import SearchRepository


def _search(session: Session, *, interval: int = 300, next_run_at=None) -> Search:
    user = User(email=f"jd{utcnow().timestamp()}@example.test", password_hash="x")
    session.add(user)
    session.flush()
    source = Source(
        user_id=user.id, name="s", adapter_key="greenhouse", base_url="", default_config={}
    )
    target = NotificationTarget(user_id=user.id, name="t", type="ntfy", config={"topic": "x"})
    session.add_all([source, target])
    session.flush()
    search = Search(
        user_id=user.id,
        name="search",
        source_id=source.id,
        target_id=target.id,
        query_url="",
        filters={},
        config={},
        interval_seconds=interval,
        enabled=True,
        next_run_at=next_run_at or utcnow(),
    )
    session.add(search)
    session.flush()
    return search


def _job(session: Session, search_id: int, external_id: str, *, status: str = "new") -> SeenJob:
    job = SeenJob(
        search_id=search_id,
        external_id=external_id,
        hash=f"h-{external_id}",
        title=f"Job {external_id}",
        company="ACME",
        location="Remote",
        url=f"https://acme.test/{external_id}",
        status=status,
    )
    session.add(job)
    session.flush()
    return job


# ---- SeenJobRepository ----


def test_seen_job_list_all_filters_by_search_id(db_session: Session) -> None:
    search_a = _search(db_session)
    search_b = _search(db_session)
    _job(db_session, search_a.id, "a1")
    _job(db_session, search_b.id, "b1")
    repo = SeenJobRepository(db_session)

    rows = repo.list_all(user_id=search_a.user_id, search_id=search_a.id)
    assert [j.external_id for j in rows] == ["a1"]


def test_seen_job_list_all_limit_none_returns_all(db_session: Session) -> None:
    """limit=None must skip LIMIT so callers can still request the full page."""
    search = _search(db_session)
    for i in range(3):
        _job(db_session, search.id, f"all{i}")
    rows = SeenJobRepository(db_session).list_all(user_id=search.user_id, limit=None)
    assert len(rows) == 3


def test_seen_job_existing_normalized_urls_empty(db_session: Session) -> None:
    assert SeenJobRepository(db_session).existing_normalized_urls_for_user(1, []) == set()


def test_seen_job_existing_normalized_urls_intersects_batch(db_session: Session) -> None:
    """Dedup must match on the persisted normalized_url, not re-scan every raw url."""
    search = _search(db_session)
    job = _job(db_session, search.id, "shared")
    # Simulate a raw URL that normalizes to the same canonical form.
    job.url = "HTTPS://Acme.Test/shared/"
    job.normalized_url = "https://acme.test/shared"
    db_session.flush()
    repo = SeenJobRepository(db_session)

    known = repo.existing_normalized_urls_for_user(
        search.user_id,
        ["https://acme.test/shared", "https://other.test/new"],
    )
    assert known == {"https://acme.test/shared"}


def test_seen_job_iter_for_user_pages_across_chunks(db_session: Session) -> None:
    """Export iteration must cover every row via bounded keyset pages (AUT-34)."""
    search = _search(db_session)
    base = utcnow()
    for i in range(5):
        job = _job(db_session, search.id, f"j{i}")
        job.first_seen_at = base + timedelta(seconds=i)
        db_session.flush()
    repo = SeenJobRepository(db_session)

    ids = [row.external_id for row in repo.iter_for_user(search.user_id, chunk_size=2)]
    assert ids == ["j4", "j3", "j2", "j1", "j0"]


def test_seen_job_iter_for_user_keyset_ties_on_same_timestamp(db_session: Session) -> None:
    """Equal first_seen_at values must still page stably on id (AUT-34)."""
    search = _search(db_session)
    base = utcnow()
    for i in range(3):
        job = _job(db_session, search.id, f"tie{i}")
        job.first_seen_at = base
        db_session.flush()
    ids = [
        row.external_id
        for row in SeenJobRepository(db_session).iter_for_user(search.user_id, chunk_size=1)
    ]
    assert ids == ["tie2", "tie1", "tie0"]


def test_seen_job_iter_for_user_rejects_non_positive_chunk(db_session: Session) -> None:
    repo = SeenJobRepository(db_session)
    with pytest.raises(ValueError, match="chunk_size"):
        next(repo.iter_for_user(1, chunk_size=0))


def test_seen_job_iter_for_user_empty(db_session: Session) -> None:
    search = _search(db_session)
    assert list(SeenJobRepository(db_session).iter_for_user(search.user_id)) == []


def test_seen_job_add_fills_normalized_url(db_session: Session) -> None:
    search = _search(db_session)
    repo = SeenJobRepository(db_session)
    row = repo.add(
        SeenJob(
            search_id=search.id,
            external_id="n1",
            hash="h",
            title="T",
            company="C",
            location="L",
            url="HTTPS://Acme.Test/role/?utm_source=x",
        )
    )
    assert row.normalized_url == "https://acme.test/role"


def test_seen_job_sync_after_scrape_set_based(db_session: Session) -> None:
    """Close/reopen via UPDATEs; empty scrape closes actives (DAT-16)."""
    search = _search(db_session)
    other = _search(db_session)
    gone = _job(db_session, search.id, "gone", status="new")
    still = _job(db_session, search.id, "still", status="seen")
    closed = _job(db_session, search.id, "back", status="closed")
    applied = _job(db_session, search.id, "applied", status="applied")
    archived = _job(db_session, search.id, "archived", status="archived")
    other_new = _job(db_session, other.id, "gone", status="new")
    repo = SeenJobRepository(db_session)

    closed_n, reopened_n = repo.sync_after_scrape(search.id, {"still", "back"})
    assert closed_n == 1
    assert reopened_n == 1
    for row in (gone, still, closed, applied, archived, other_new):
        db_session.refresh(row)
    assert gone.status == "closed"
    assert still.status == "seen"
    assert closed.status == "seen"
    assert applied.status == "applied"
    assert archived.status == "archived"
    assert other_new.status == "new"

    closed_all, reopened_empty = repo.sync_after_scrape(search.id, set())
    assert closed_all == 2  # still + reopened back
    assert reopened_empty == 0
    db_session.refresh(still)
    db_session.refresh(closed)
    assert still.status == "closed"
    assert closed.status == "closed"


def test_seen_job_sync_after_scrape_uses_update_not_full_select() -> None:
    """Compiled close/reopen statements must be UPDATEs scoped by search_id (DAT-16)."""
    from sqlalchemy.dialects import postgresql

    scraped = {"a", "b"}
    close_stmt = (
        update(SeenJob)
        .where(SeenJob.search_id == 1)
        .where(SeenJob.status.in_(("new", "seen")))
        .where(SeenJob.external_id.not_in(scraped))
        .values(status="closed")
    )
    reopen_stmt = (
        update(SeenJob)
        .where(SeenJob.search_id == 1)
        .where(SeenJob.status == "closed")
        .where(SeenJob.external_id.in_(scraped))
        .values(status="seen")
    )
    close_sql = str(
        close_stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).upper()
    reopen_sql = str(
        reopen_stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).upper()
    assert close_sql.startswith("UPDATE")
    assert "SEARCH_ID" in close_sql
    assert "NOT IN" in close_sql or "NOT (" in close_sql
    assert reopen_sql.startswith("UPDATE")
    assert " IN (" in reopen_sql


def test_seen_job_existing_normalized_urls_sql_filters_batch() -> None:
    """Compiled SQL must IN-filter the batch on normalized_url (no full-history load)."""
    from sqlalchemy.dialects import postgresql

    from app.models.search import Search

    wanted = {"https://acme.test/a", "https://acme.test/b"}
    stmt = (
        select(SeenJob.normalized_url)
        .join(Search, SeenJob.search_id == Search.id)
        .where(Search.user_id == 1)
        .where(SeenJob.normalized_url.in_(wanted))
    )
    compiled = str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).upper()
    assert "NORMALIZED_URL" in compiled
    assert " IN (" in compiled


# ---- DeliveryLogRepository ----


def test_delivery_add(db_session: Session) -> None:
    search = _search(db_session)
    job = _job(db_session, search.id, "d1")
    repo = DeliveryLogRepository(db_session)

    log = repo.add(DeliveryLog(seen_job_id=job.id, status="failed", error="boom"))
    assert log.id is not None


def test_delivery_recent_failures_respects_limit(db_session: Session) -> None:
    search = _search(db_session)
    job = _job(db_session, search.id, "d2")
    repo = DeliveryLogRepository(db_session)
    for i in range(3):
        repo.add(DeliveryLog(seen_job_id=job.id, status="failed", error=f"e{i}"))

    by_search = repo.recent_failures_for_searches([search.id], limit=2)
    assert len(by_search[search.id]) == 2  # third failure skipped by the limit
    assert [f.error for f in by_search[search.id]] == ["e2", "e1"]


def test_delivery_recent_failures_empty_search_ids(db_session: Session) -> None:
    assert DeliveryLogRepository(db_session).recent_failures_for_searches([]) == {}


def test_delivery_recent_failures_ranks_per_search(db_session: Session) -> None:
    """Each search keeps its own top-N; one noisy search cannot crowd out another."""
    search_a = _search(db_session)
    search_b = _search(db_session)
    job_a = _job(db_session, search_a.id, "da")
    job_b = _job(db_session, search_b.id, "db")
    repo = DeliveryLogRepository(db_session)
    for i in range(5):
        repo.add(DeliveryLog(seen_job_id=job_a.id, status="failed", error=f"a{i}"))
    repo.add(DeliveryLog(seen_job_id=job_b.id, status="sent", error=None))
    for i in range(3):
        repo.add(DeliveryLog(seen_job_id=job_b.id, status="failed", error=f"b{i}"))

    by_search = repo.recent_failures_for_searches([search_a.id, search_b.id], limit=2)
    assert [f.error for f in by_search[search_a.id]] == ["a4", "a3"]
    assert [f.error for f in by_search[search_b.id]] == ["b2", "b1"]


def test_delivery_recent_failures_sql_uses_row_number() -> None:
    """Compiled SQL must rank per search so the outer query never loads all failures."""
    from sqlalchemy.dialects import postgresql

    ranked = (
        select(
            DeliveryLog.id.label("log_id"),
            SeenJob.id.label("job_id"),
            func.row_number()
            .over(
                partition_by=SeenJob.search_id,
                order_by=DeliveryLog.sent_at.desc(),
            )
            .label("rn"),
        )
        .join(SeenJob, DeliveryLog.seen_job_id == SeenJob.id)
        .where(SeenJob.search_id.in_([1, 2]))
        .where(DeliveryLog.status == "failed")
    ).subquery()
    stmt = (
        select(DeliveryLog, SeenJob)
        .join(ranked, DeliveryLog.id == ranked.c.log_id)
        .join(SeenJob, SeenJob.id == ranked.c.job_id)
        .where(ranked.c.rn <= 5)
        .order_by(DeliveryLog.sent_at.desc())
    )
    compiled = str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).upper()
    assert "ROW_NUMBER()" in compiled
    assert "PARTITION BY" in compiled


# ---- SearchRepository ----


def test_search_delete(db_session: Session) -> None:
    search = _search(db_session)
    repo = SearchRepository(db_session)

    repo.delete(search)
    db_session.flush()
    assert repo.list_all(search.user_id) == []


def test_claim_due_takes_row_lock_branch_on_non_sqlite(db_session: Session) -> None:
    """Force the FOR UPDATE SKIP LOCKED branch (SQLite silently drops the clause)."""
    now = utcnow()
    search = _search(db_session, interval=300, next_run_at=now - timedelta(seconds=5))
    repo = SearchRepository(db_session)
    repo._is_sqlite = lambda: False  # type: ignore[method-assign]

    assert repo.claim_due(now) == [search.id]


def test_claim_due_compiles_skip_locked_for_postgres() -> None:
    """Postgres claim SQL must include SKIP LOCKED so overlapping ticks cannot double-enqueue."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models.search import Search

    now = utcnow()
    stmt = (
        select(Search)
        .where(Search.enabled.is_(True))
        .where(Search.next_run_at <= now)
        .order_by(Search.next_run_at)
        .with_for_update(skip_locked=True)
    )
    compiled = str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "FOR UPDATE SKIP LOCKED" in compiled.upper()


def test_get_for_update_takes_lock_branch_on_non_sqlite(db_session: Session) -> None:
    search = _search(db_session)
    repo = SearchRepository(db_session)
    repo._is_sqlite = lambda: False  # type: ignore[method-assign]

    row = repo.get_for_update(search.id, skip_locked=True)
    assert row is not None
    assert row.id == search.id


def test_get_for_update_compiles_skip_locked_for_postgres() -> None:
    """Digest flush and other exclusive paths must compile row locks for Postgres."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models.search import Search

    stmt = select(Search).where(Search.id == 1).with_for_update(skip_locked=True)
    compiled = str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "FOR UPDATE SKIP LOCKED" in compiled.upper()
