"""Data access for SeenJob (the dedup ledger + job feed)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.search import Search
from app.models.seen_job import SeenJob
from app.scrapers.url import normalize_job_url


class SeenJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self, *, user_id: int, search_id: int | None = None, limit: int = 100
    ) -> list[SeenJob]:
        # Jobs are owned transitively through their search, so scope by the
        # search's owner rather than adding a redundant column to seen_job.
        stmt = (
            select(SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .order_by(SeenJob.first_seen_at.desc())
            .limit(limit)
        )
        if search_id is not None:
            stmt = stmt.where(SeenJob.search_id == search_id)
        return list(self.session.scalars(stmt))

    def existing_external_ids(self, search_id: int, external_ids: list[str]) -> set[str]:
        """Return the subset of external_ids already seen for a search."""
        if not external_ids:
            return set()
        stmt = (
            select(SeenJob.external_id)
            .where(SeenJob.search_id == search_id)
            .where(SeenJob.external_id.in_(external_ids))
        )
        return set(self.session.scalars(stmt))

    def existing_normalized_urls_for_user(
        self, user_id: int, normalized_urls: list[str]
    ) -> set[str]:
        """Return normalized URLs already recorded in any of the user's searches."""
        if not normalized_urls:
            return set()
        wanted = set(normalized_urls)
        stmt = (
            select(SeenJob.url)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .where(SeenJob.url != "")
        )
        known = {normalize_job_url(url) for url in self.session.scalars(stmt)}
        return wanted & known

    def add(self, seen_job: SeenJob) -> SeenJob:
        self.session.add(seen_job)
        self.session.flush()
        return seen_job
