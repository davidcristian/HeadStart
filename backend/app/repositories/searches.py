"""Data access for Search, including the due-search query used by the scheduler."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.search import Search


class SearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, user_id: int) -> list[Search]:
        return list(
            self.session.scalars(
                select(Search).where(Search.user_id == user_id).order_by(Search.id)
            )
        )

    def get(self, search_id: int, user_id: int | None = None) -> Search | None:
        """Fetch a search. Pass `user_id` to enforce ownership (API paths).

        The worker pipeline calls this without a `user_id` because it already
        selected the search via the global `due()` query.
        """
        if user_id is None:
            return self.session.get(Search, search_id)
        return self.session.scalar(
            select(Search).where(Search.id == search_id, Search.user_id == user_id)
        )

    def add(self, search: Search) -> Search:
        self.session.add(search)
        self.session.flush()
        return search

    def delete(self, search: Search) -> None:
        self.session.delete(search)

    def due(self, now: datetime) -> list[Search]:
        """Enabled searches whose next_run_at is in the past (i.e. due/overdue)."""
        stmt = (
            select(Search)
            .where(Search.enabled.is_(True))
            .where(Search.next_run_at <= now)
            .order_by(Search.next_run_at)
        )
        return list(self.session.scalars(stmt))
