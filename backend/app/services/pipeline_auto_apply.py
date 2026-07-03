"""Pipeline hook: queue live applies for newly discovered jobs."""

from __future__ import annotations

from app.models.seen_job import SeenJob
from app.scrapers.types import JobPosting
from app.services.apply import ApplyService, QueuedAutoApply


def queue_auto_applies_for_new_jobs(
    apply_service: ApplyService,
    user_id: int,
    postings: list[JobPosting],
    seen_rows: dict[str, SeenJob],
) -> list[QueuedAutoApply]:
    """Enqueue live applies when the source has auto-apply enabled and profile is set."""
    pending: list[QueuedAutoApply] = []
    for posting in postings:
        row = seen_rows.get(posting.external_id)
        if row is None:
            continue
        queued = apply_service.enqueue_auto_apply_from_pipeline(user_id, row.id)
        if queued is not None:
            pending.append(queued)
    return pending
