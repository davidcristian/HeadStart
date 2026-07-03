"""Data access for inbox ghost detection on stale applications."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.search import Search
from app.models.seen_job import SeenJob


class GhostDetectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_stale_applications(self, *, cutoff: datetime) -> list[tuple[int, SeenJob]]:
        """Return (user_id, job) pairs past the ghost silence window and not yet ghosted."""
        stmt = (
            select(Search.user_id, SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(
                SeenJob.status == "applied",
                SeenJob.applied_at.is_not(None),
                SeenJob.applied_at <= cutoff,
                SeenJob.ghosted_at.is_(None),
            )
            .options(joinedload(SeenJob.application_logs))
            .order_by(SeenJob.applied_at.asc())
        )
        rows = self.session.execute(stmt).unique().all()
        return [(int(user_id), job) for user_id, job in rows]
