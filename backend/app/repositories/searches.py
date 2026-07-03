"""Data access for Search, including the due-search query used by the scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta

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

    def claim_due(self, now: datetime) -> list[int]:
        """Atomically claim due searches for this beat tick, advancing next_run_at so
        an overlapping tick (or a scrape slower than the beat interval) cannot
        re-enqueue the same search and double-notify. Returns the claimed ids.

        On Postgres the due rows are locked with FOR UPDATE SKIP LOCKED so concurrent
        workers claim disjoint sets; SQLite (tests) has no row-level locking.
        """
        stmt = (
            select(Search)
            .where(Search.enabled.is_(True))
            .where(Search.next_run_at <= now)
            .order_by(Search.next_run_at)
        )
        if not self._is_sqlite():
            stmt = stmt.with_for_update(skip_locked=True)
        searches = list(self.session.scalars(stmt))
        for search in searches:
            # Same schedule as services.scheduling.next_run_from; inlined so the
            # repository does not import from the services layer.
            search.next_run_at = now + timedelta(seconds=max(search.interval_seconds, 1))
        self.session.flush()
        return [search.id for search in searches]

    def get_for_update(self, search_id: int, *, skip_locked: bool = False) -> Search | None:
        """Fetch a search holding a row lock for exclusive processing (Postgres).

        Returns None when `skip_locked` is set and another transaction holds the
        lock. SQLite (tests) has no row locking, so it always returns the row.
        """
        if self._is_sqlite():
            return self.session.get(Search, search_id)
        stmt = select(Search).where(Search.id == search_id).with_for_update(skip_locked=skip_locked)
        return self.session.scalar(stmt)

    def _is_sqlite(self) -> bool:
        return self.session.get_bind().dialect.name == "sqlite"
