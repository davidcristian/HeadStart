"""Direct unit tests for SeenJob, DeliveryLog, and Search repositories."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
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


def test_seen_job_existing_normalized_urls_empty(db_session: Session) -> None:
    assert SeenJobRepository(db_session).existing_normalized_urls_for_user(1, []) == set()


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
