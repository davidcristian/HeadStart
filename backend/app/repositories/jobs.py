"""Data access for SeenJob (the dedup ledger + job feed)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.models.search import Search
from app.models.seen_job import SeenJob
from app.scrapers.url import normalize_job_url

# GDPR export walks the full ledger in bounded SELECTs (AUT-34).
DEFAULT_EXPORT_JOBS_CHUNK_SIZE = 500


class SeenJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self,
        *,
        user_id: int,
        search_id: int | None = None,
        status: str | None = None,
        limit: int | None = 100,
    ) -> list[SeenJob]:
        # Jobs are owned transitively through their search, so scope by the
        # search's owner rather than adding a redundant column to seen_job.
        stmt = (
            select(SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .order_by(SeenJob.first_seen_at.desc(), SeenJob.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if search_id is not None:
            stmt = stmt.where(SeenJob.search_id == search_id)
        if status is not None:
            stmt = stmt.where(SeenJob.status == status)
        return list(self.session.scalars(stmt))

    def iter_for_user(
        self,
        user_id: int,
        *,
        chunk_size: int = DEFAULT_EXPORT_JOBS_CHUNK_SIZE,
    ) -> Iterator[SeenJob]:
        """Yield every owned job newest-first via keyset pages (no unbounded SELECT)."""
        if chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")
        cursor_seen_at: datetime | None = None
        cursor_id: int | None = None
        while True:
            stmt = (
                select(SeenJob)
                .join(Search, SeenJob.search_id == Search.id)
                .where(Search.user_id == user_id)
                .order_by(SeenJob.first_seen_at.desc(), SeenJob.id.desc())
                .limit(chunk_size)
            )
            if cursor_seen_at is not None and cursor_id is not None:
                stmt = stmt.where(
                    or_(
                        SeenJob.first_seen_at < cursor_seen_at,
                        and_(
                            SeenJob.first_seen_at == cursor_seen_at,
                            SeenJob.id < cursor_id,
                        ),
                    )
                )
            rows = list(self.session.scalars(stmt))
            if not rows:
                break
            yield from rows
            if len(rows) < chunk_size:
                break
            last = rows[-1]
            cursor_seen_at = last.first_seen_at
            cursor_id = last.id

    def get(self, job_id: int, user_id: int) -> SeenJob | None:
        stmt = (
            select(SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(SeenJob.id == job_id, Search.user_id == user_id)
        )
        return self.session.scalar(stmt)

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
            select(SeenJob.normalized_url)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .where(SeenJob.normalized_url.in_(wanted))
        )
        return set(self.session.scalars(stmt))

    def add(self, seen_job: SeenJob) -> SeenJob:
        # Keep the indexed column in sync when callers only set url (DAT-05).
        if not seen_job.normalized_url and seen_job.url:
            seen_job.normalized_url = normalize_job_url(seen_job.url)
        self.session.add(seen_job)
        self.session.flush()
        return seen_job

    def sync_after_scrape(self, search_id: int, scraped_external_ids: set[str]) -> tuple[int, int]:
        """Close missing listings and reopen reappeared ones via set-based UPDATEs (DAT-16)."""
        close_stmt = (
            update(SeenJob)
            .where(SeenJob.search_id == search_id)
            .where(SeenJob.status.in_(("new", "seen")))
            .values(status="closed")
        )
        if scraped_external_ids:
            close_stmt = close_stmt.where(SeenJob.external_id.not_in(scraped_external_ids))
        closed = int(getattr(self.session.execute(close_stmt), "rowcount", 0) or 0)

        reopened = 0
        if scraped_external_ids:
            reopen_stmt = (
                update(SeenJob)
                .where(SeenJob.search_id == search_id)
                .where(SeenJob.status == "closed")
                .where(SeenJob.external_id.in_(scraped_external_ids))
                .values(status="seen")
            )
            reopened = int(getattr(self.session.execute(reopen_stmt), "rowcount", 0) or 0)
        return closed, reopened
