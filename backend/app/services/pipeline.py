"""The per-search pipeline: scrape -> filter -> dedupe -> notify -> record -> reschedule.

This is plain business logic with no Celery/HTTP framework coupling, so it can be
unit-tested directly and driven by the worker. Scraper/notifier resolution is
injected to make testing trivial (no network).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import record_notification, record_pipeline_run, record_scrape
from app.models.base import utcnow
from app.models.delivery_log import DeliveryLog
from app.models.seen_job import SeenJob
from app.notifiers import NotifyContext, get_notifier
from app.notifiers.base import Notifier
from app.repositories.jobs import SeenJobRepository
from app.repositories.searches import SearchRepository
from app.scrapers import ScrapeContext, get_scraper
from app.scrapers.base import Scraper
from app.scrapers.http import HttpClient
from app.scrapers.rate_limit import RateLimiter, resolve_min_interval
from app.scrapers.types import JobPosting
from app.scrapers.url import normalize_job_url
from app.services.compensation import format_compensation_display
from app.services.credentials import CredentialService
from app.services.digest import DigestService
from app.services.posting_filters import apply_posting_filters
from app.services.scheduling import next_run_from

logger = get_logger(__name__)

ScraperFactory = Callable[..., Scraper]
NotifierFactory = Callable[[str], Notifier]


@dataclass
class RunResult:
    search_id: int
    found: int = 0
    new: int = 0
    notified: int = 0
    failed: int = 0
    skipped: int = 0
    filtered: int = 0
    queued: int = 0
    closed: int = 0
    error: str | None = None


class PipelineService:
    def __init__(
        self,
        session: Session,
        *,
        scraper_factory: ScraperFactory = get_scraper,
        notifier_factory: NotifierFactory = get_notifier,
    ) -> None:
        self.session = session
        self.searches = SearchRepository(session)
        self.seen_jobs = SeenJobRepository(session)
        self.credentials = CredentialService(session)
        self.digest = DigestService(session, notifier_factory=notifier_factory)
        self._scraper_factory = scraper_factory
        self._notifier_factory = notifier_factory

    def run(self, search_id: int) -> RunResult:
        search = self.searches.get(search_id)
        if search is None:
            logger.warning("run_search: search %s no longer exists", search_id)
            record_pipeline_run("not_found")
            return RunResult(search_id=search_id, error="not found")

        result = RunResult(search_id=search_id)
        try:
            postings = self.scrape(
                adapter_key=search.source.adapter_key,
                user_id=search.user_id,
                source_id=search.source_id,
                query_url=search.query_url,
                filters=search.filters,
                config={**search.source.default_config, **search.config},
            )
            result.found = len(postings)
            scraped_ids = {p.external_id for p in postings}
            closed, _reopened = self.seen_jobs.sync_after_scrape(search_id, scraped_ids)
            result.closed = closed
            postings, result.filtered = apply_posting_filters(postings, search.filters)
            new_postings = self._dedupe(search_id, postings)
            result.new = len(new_postings)
            to_notify, result.skipped = self._filter_cross_search(search.user_id, new_postings)
            seen_rows = self._persist_new(search_id, new_postings)
            if to_notify:
                if search.notification_mode == "digest":
                    result.queued = self._queue_digest(search_id, to_notify, seen_rows)
                else:
                    sent, failed = self._notify(search, to_notify, seen_rows)
                    result.notified, result.failed = sent, failed
        except Exception as exc:  # adapters/network are untrusted; never crash the worker
            logger.exception("run_search %s failed: %s", search_id, exc)
            result.error = str(exc)
            record_pipeline_run("error")
        else:
            record_pipeline_run("success")
        finally:
            self._reschedule(search_id, last_error=result.error)
        return result

    def scrape(
        self,
        *,
        adapter_key: str,
        user_id: int,
        source_id: int,
        query_url: str,
        filters: dict[str, Any],
        config: dict[str, Any],
    ) -> list[JobPosting]:
        """Fetch postings once without persisting or notifying."""
        cookies, headers = self._resolve_credentials(user_id, source_id)
        min_interval = resolve_min_interval(adapter_key, config)
        rate_limiter = RateLimiter(min_interval) if min_interval > 0 else None
        if cookies or headers or rate_limiter:
            http = HttpClient(headers=headers, cookies=cookies, rate_limiter=rate_limiter)
        else:
            http = None
        scraper = self._scraper_factory(adapter_key, http, rate_limiter)
        ctx = ScrapeContext(
            query_url=query_url,
            filters=filters,
            config=config,
            cookies=cookies,
            headers=headers,
        )
        start = time.perf_counter()
        try:
            postings = scraper.fetch(ctx)
        except Exception:
            record_scrape(adapter_key, "error", time.perf_counter() - start, 0)
            raise
        record_scrape(adapter_key, "success", time.perf_counter() - start, len(postings))
        return postings

    def _resolve_credentials(
        self, user_id: int, source_id: int
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Return (cookies, headers) for the user+source, empty dicts if none."""
        secret = self.credentials.secret_for_source(user_id, source_id)
        if not secret:
            return {}, {}
        return secret.get("cookies", {}), secret.get("headers", {})

    def _dedupe(self, search_id: int, postings: list[JobPosting]) -> list[JobPosting]:
        # Drop duplicates within the batch first, then against the database.
        by_external: dict[str, JobPosting] = {}
        for posting in postings:
            by_external.setdefault(posting.external_id, posting)
        existing = self.seen_jobs.existing_external_ids(search_id, list(by_external))
        return [p for ext, p in by_external.items() if ext not in existing]

    def _filter_cross_search(
        self, user_id: int, postings: list[JobPosting]
    ) -> tuple[list[JobPosting], int]:
        """Skip notification when the same job URL was already seen in another search."""
        if not postings:
            return [], 0

        by_url: dict[str, JobPosting] = {}
        without_url: list[JobPosting] = []
        for posting in postings:
            normalized = normalize_job_url(posting.url)
            if normalized:
                by_url.setdefault(normalized, posting)
            else:
                without_url.append(posting)

        known_urls = self.seen_jobs.existing_normalized_urls_for_user(user_id, list(by_url))
        to_notify = list(without_url)
        skipped = 0
        for normalized, posting in by_url.items():
            if normalized in known_urls:
                skipped += 1
                continue
            known_urls.add(normalized)
            to_notify.append(posting)
        return to_notify, skipped

    def _persist_new(self, search_id: int, postings: list[JobPosting]) -> dict[str, SeenJob]:
        rows: dict[str, SeenJob] = {}
        for posting in postings:
            row = SeenJob(
                search_id=search_id,
                external_id=posting.external_id,
                hash=posting.content_hash(),
                title=posting.title,
                company=posting.company,
                location=posting.location,
                salary=format_compensation_display(posting),
                url=posting.url,
            )
            self.seen_jobs.add(row)
            rows[posting.external_id] = row
        return rows

    def _queue_digest(
        self,
        search_id: int,
        postings: list[JobPosting],
        seen_rows: dict[str, SeenJob],
    ) -> int:
        seen_job_ids = [
            seen_rows[posting.external_id].id
            for posting in postings
            if posting.external_id in seen_rows
        ]
        return self.digest.queue(search_id, seen_job_ids)

    def _notify(
        self,
        search: object,
        postings: list[JobPosting],
        seen_rows: dict[str, SeenJob],
    ) -> tuple[int, int]:
        target = search.target  # type: ignore[attr-defined]
        if target is None:
            logger.info("search %s has no target; skipping notification", search.id)  # type: ignore[attr-defined]
            return 0, 0
        notifier = self._notifier_factory(target.type)
        results = notifier.send(
            NotifyContext(target_type=target.type, config=target.config), postings
        )
        sent = failed = 0
        for res in results:
            row = seen_rows.get(res.external_id)
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
            if res.status == "sent":
                sent += 1
            else:
                failed += 1
            record_notification(target.type, res.status, "immediate")  # type: ignore[arg-type]
        return sent, failed

    def _reschedule(self, search_id: int, *, last_error: str | None = None) -> None:
        search = self.searches.get(search_id)
        if search is None:
            return
        now = utcnow()
        search.last_run_at = now
        search.last_error = last_error
        search.next_run_at = next_run_from(now, search.interval_seconds)
        self.session.flush()
