"""Digest notification queueing and periodic flush."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import record_digest_flush, record_notification
from app.models.base import utcnow
from app.models.delivery_log import DeliveryLog
from app.models.pending_digest import PendingDigest
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.notifiers import NotifyContext, get_notifier
from app.notifiers.base import Notifier
from app.repositories.digest import PendingDigestRepository
from app.repositories.searches import SearchRepository
from app.scrapers.types import JobPosting

logger = get_logger(__name__)

NotifierFactory = Callable[[str], Notifier]


class DigestService:
    def __init__(
        self,
        session: Session,
        *,
        notifier_factory: NotifierFactory = get_notifier,
    ) -> None:
        self.session = session
        self.searches = SearchRepository(session)
        self.pending = PendingDigestRepository(session)
        self._notifier_factory = notifier_factory

    def queue(self, search_id: int, seen_job_ids: list[int]) -> int:
        """Enqueue seen jobs for a later batched digest notification."""
        queued = 0
        for seen_job_id in seen_job_ids:
            self.pending.add(search_id, seen_job_id)
            queued += 1
        return queued

    def flush_due(self, now: datetime | None = None) -> int:
        """Send batched digests for searches whose interval has elapsed."""
        when = now or utcnow()
        flushed = 0
        for search in self.pending.searches_with_pending():
            pending = self.pending.list_for_search(search.id)
            if not pending or not self._is_due(search, pending, when):
                continue
            self._flush_search(search, pending)
            flushed += 1
        return flushed

    def _is_due(self, search: Search, pending: list[PendingDigest], now: datetime) -> bool:
        interval = timedelta(seconds=search.digest_interval_seconds)
        oldest = _as_utc(min(row.created_at for row in pending))
        when = _as_utc(now)
        last_digest = _as_utc(search.last_digest_at) if search.last_digest_at else None
        if last_digest is None:
            return when >= oldest + interval
        return when >= last_digest + interval

    def _flush_search(self, search: Search, pending: list[PendingDigest]) -> None:
        loaded = self.searches.get(search.id)
        if loaded is None:
            return
        target = loaded.target
        if target is None:
            return
        search = loaded

        seen_rows: list[SeenJob] = [row.seen_job for row in pending]
        postings = [_seen_job_to_posting(row) for row in seen_rows]
        notifier = self._notifier_factory(target.type)
        try:
            results = notifier.send(
                NotifyContext(
                    target_type=target.type,
                    config=target.config,
                    digest=True,
                    search_name=search.name,
                ),
                postings,
            )
        except Exception:
            record_digest_flush("error")
            raise
        by_external = {row.external_id: row for row in seen_rows}
        for res in results:
            row = by_external.get(res.external_id)
            if row is None:
                continue
            self.session.add(
                DeliveryLog(
                    seen_job_id=row.id,
                    target_id=target.id,
                    status=res.status,
                    error=res.error,
                )
            )
            record_notification(target.type, res.status, "digest")  # type: ignore[arg-type]
        self.pending.delete_for_search(search.id)
        search.last_digest_at = utcnow()
        self.session.flush()
        record_digest_flush("success")
        logger.info(
            "digest flush search %s: %d job(s), sent=%d failed=%d",
            search.id,
            len(postings),
            sum(1 for r in results if r.status == "sent"),
            sum(1 for r in results if r.status == "failed"),
        )


def _seen_job_to_posting(row: SeenJob) -> JobPosting:
    return JobPosting(
        external_id=row.external_id,
        title=row.title,
        company=row.company,
        location=row.location,
        url=row.url,
    )


def _as_utc(dt: datetime) -> datetime:
    """Coerce to tz-aware UTC. SQLite returns naive datetimes; Postgres does not."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
