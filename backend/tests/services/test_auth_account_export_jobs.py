"""GDPR export job ledger is walked in bounded chunks."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.repositories.jobs import SeenJobRepository
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthService
from app.services.auth_account_export import build_user_data_export


def _seed_jobs(session: Session, user_id: int, count: int) -> Search:
    source = Source(
        user_id=user_id,
        name="s",
        adapter_key="greenhouse",
        base_url="",
        default_config={},
    )
    target = NotificationTarget(user_id=user_id, name="t", type="ntfy", config={"topic": "x"})
    session.add_all([source, target])
    session.flush()
    search = Search(
        user_id=user_id,
        name="search",
        source_id=source.id,
        target_id=target.id,
        query_url="",
        filters={},
        config={},
        interval_seconds=300,
        enabled=True,
        next_run_at=utcnow(),
    )
    session.add(search)
    session.flush()
    base = utcnow()
    for i in range(count):
        job = SeenJob(
            search_id=search.id,
            external_id=f"ext-{i}",
            hash=f"h-{i}",
            title=f"Job {i}",
            company="ACME",
            location="Remote",
            url=f"https://acme.test/{i}",
            status="new",
            first_seen_at=base + timedelta(seconds=i),
        )
        session.add(job)
    session.flush()
    return search


def test_export_jobs_uses_chunked_iteration(db_session: Session) -> None:
    user = AuthService(db_session).register(
        RegisterRequest(email="export-jobs@example.com", password="password123")
    )
    assert user is not None
    _seed_jobs(db_session, user.id, count=5)
    calls: list[int] = []
    real_iter = SeenJobRepository.iter_for_user

    def tracking_iter(self: SeenJobRepository, user_id: int, *, chunk_size: int = 500):
        calls.append(chunk_size)
        yield from real_iter(self, user_id, chunk_size=chunk_size)

    with patch.object(SeenJobRepository, "iter_for_user", tracking_iter):
        export = build_user_data_export(db_session, user, jobs_chunk_size=2)

    assert calls == [2]
    assert [job.external_id for job in export.jobs] == [
        "ext-4",
        "ext-3",
        "ext-2",
        "ext-1",
        "ext-0",
    ]
    # Chunked path expunges each ORM row after JobRead serialization.
    assert not any(isinstance(obj, SeenJob) for obj in db_session.identity_map.values())
