"""Data access for SearchRun."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.search_run import SearchRun


class SearchRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: SearchRun) -> SearchRun:
        """Persist a new search run and flush so ``id`` is available."""
        self.session.add(row)
        self.session.flush()
        return row

    def get_for_user(self, run_id: int, user_id: int) -> SearchRun | None:
        """Return one search run owned by ``user_id``."""
        stmt = select(SearchRun).where(SearchRun.id == run_id, SearchRun.user_id == user_id)
        return self.session.scalar(stmt)

    def get(self, run_id: int) -> SearchRun | None:
        """Return one search run by primary key."""
        return self.session.get(SearchRun, run_id)
