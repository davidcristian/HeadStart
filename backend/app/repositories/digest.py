"""Data access for the digest notification queue."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models.pending_digest import PendingDigest
from app.models.search import Search


class PendingDigestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, search_id: int, seen_job_id: int) -> PendingDigest:
        """Enqueue one seen job (single-row convenience over ``add_many``)."""
        return self.add_many(search_id, [seen_job_id])[0]

    def add_many(self, search_id: int, seen_job_ids: list[int]) -> list[PendingDigest]:
        """Enqueue many seen jobs with one flush (SVC-15)."""
        if not seen_job_ids:
            return []
        rows = [
            PendingDigest(search_id=search_id, seen_job_id=seen_job_id)
            for seen_job_id in seen_job_ids
        ]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def list_for_search(self, search_id: int) -> list[PendingDigest]:
        return list(
            self.session.scalars(
                select(PendingDigest)
                .where(PendingDigest.search_id == search_id)
                .options(joinedload(PendingDigest.seen_job))
                .order_by(PendingDigest.created_at)
            )
        )

    def delete_for_search(self, search_id: int) -> None:
        """Clear the digest queue for a search in one statement (DAT-13)."""
        self.session.execute(delete(PendingDigest).where(PendingDigest.search_id == search_id))

    def searches_with_pending(self) -> list[Search]:
        """Enabled digest-mode searches that have at least one queued job."""
        stmt = (
            select(Search)
            .join(PendingDigest, PendingDigest.search_id == Search.id)
            .where(Search.enabled.is_(True))
            .where(Search.notification_mode == "digest")
            .where(Search.target_id.is_not(None))
            .distinct()
            .order_by(Search.id)
        )
        return list(self.session.scalars(stmt))
