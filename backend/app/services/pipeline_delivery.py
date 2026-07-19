"""Pipeline helpers: persist seen jobs and deliver immediate / digest notifications."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import record_notification
from app.models.delivery_log import DeliveryLog
from app.models.seen_job import SeenJob
from app.models.user import User
from app.notifiers import NotifyContext
from app.notifiers.base import Notifier
from app.repositories.jobs import SeenJobRepository
from app.scrapers.types import JobPosting
from app.scrapers.url import normalize_job_url
from app.services.compensation import format_compensation_display
from app.services.digest import DigestService

logger = get_logger(__name__)

NotifierFactory = Callable[[str], Notifier]


def persist_new_seen_jobs(
    seen_jobs: SeenJobRepository,
    search_id: int,
    postings: list[JobPosting],
) -> dict[str, SeenJob]:
    """Insert SeenJob rows for newly discovered postings; return by external_id."""
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
            normalized_url=normalize_job_url(posting.url),
            summary=posting.summary,
        )
        seen_jobs.add(row)
        rows[posting.external_id] = row
    return rows


def queue_digest_for_postings(
    digest: DigestService,
    search_id: int,
    postings: list[JobPosting],
    seen_rows: dict[str, SeenJob],
) -> int:
    """Enqueue digest rows for postings that already have a SeenJob id."""
    seen_job_ids = [
        seen_rows[posting.external_id].id
        for posting in postings
        if posting.external_id in seen_rows
    ]
    return digest.queue(search_id, seen_job_ids)


def notify_immediate(
    session: Session,
    *,
    search: object,
    postings: list[JobPosting],
    seen_rows: dict[str, SeenJob],
    notifier_factory: NotifierFactory,
) -> tuple[int, int]:
    """Send immediate notifications and write DeliveryLog rows; return (sent, failed)."""
    target = search.target  # type: ignore[attr-defined]
    if target is None:
        logger.info(
            "search %s has no target; skipping notification",
            search.id,  # type: ignore[attr-defined]
        )
        return 0, 0
    notifier = notifier_factory(target.type)
    owner = session.get(User, search.user_id)  # type: ignore[attr-defined]
    results = notifier.send(
        NotifyContext(
            target_type=target.type,
            config=target.config,
            locale=owner.locale if owner is not None else None,
        ),
        postings,
    )
    sent = failed = 0
    for res in results:
        row = seen_rows.get(res.external_id)
        if row is None:
            continue
        session.add(
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
