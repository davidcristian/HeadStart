"""Data access for inbox ghost detection on stale applications."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.search import Search
from app.models.seen_job import SeenJob


class GhostDetectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def claim_stale_applications(
        self,
        *,
        cutoff: datetime,
        now: datetime,
        limit: int = 100,
    ) -> list[tuple[int, SeenJob]]:
        """Lease stale unghosted applications so overlapping ticks cannot double-send.

        Locks candidates with ``FOR UPDATE SKIP LOCKED`` on Postgres, sets
        ``ghosted_at`` on each returned row, and flushes. The caller must commit
        the lease before SMTP so a crash/redelivery cannot re-select the same
        row. SQLite (tests) has no row-level locking; the ``ghosted_at`` stamp
        still blocks a second claim in-process. Uses ``selectinload`` (not
        ``joinedload``) so ``FOR UPDATE`` is not paired with an outer join.
        """
        stmt = (
            select(Search.user_id, SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(
                SeenJob.status == "applied",
                SeenJob.applied_at.is_not(None),
                SeenJob.applied_at <= cutoff,
                SeenJob.ghosted_at.is_(None),
            )
            .options(selectinload(SeenJob.application_logs))
            .order_by(SeenJob.applied_at.asc())
            .limit(limit)
        )
        if not self._is_sqlite():
            stmt = stmt.with_for_update(skip_locked=True, of=SeenJob)
        rows = self.session.execute(stmt).unique().all()
        claimed: list[tuple[int, SeenJob]] = []
        for user_id, job in rows:
            job.ghosted_at = now
            claimed.append((int(user_id), job))
        self.session.flush()
        return claimed

    def get_claimed(self, job_id: int) -> tuple[int, SeenJob] | None:
        """Load one leased (``ghosted_at`` set) job with its search owner."""
        stmt = (
            select(Search.user_id, SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(
                SeenJob.id == job_id,
                SeenJob.ghosted_at.is_not(None),
            )
            .options(selectinload(SeenJob.application_logs))
        )
        row = self.session.execute(stmt).unique().first()
        if row is None:
            return None
        user_id, job = row
        return int(user_id), job

    def release_claim(self, job: SeenJob) -> None:
        """Clear ``ghosted_at`` so a failed send can be retried on the next tick."""
        job.ghosted_at = None
        self.session.flush()

    def _is_sqlite(self) -> bool:
        return self.session.get_bind().dialect.name == "sqlite"
