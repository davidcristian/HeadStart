"""Celery tasks: glue between the scheduler and the pipeline service.

These are intentionally thin. All real logic lives in `app.services`.
"""

from __future__ import annotations

from dataclasses import asdict

from app.core.db import session_scope
from app.core.logging import get_logger
from app.models.base import utcnow
from app.repositories.searches import SearchRepository
from app.services.pipeline import PipelineService
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.run_search", bind=True, max_retries=0)
def run_search(self: object, search_id: int) -> dict[str, object]:
    """Run one search's pipeline (scrape -> dedupe -> notify -> record)."""
    with session_scope() as session:
        result = PipelineService(session).run(search_id)
    logger.info(
        "run_search %s: found=%d new=%d notified=%d failed=%d",
        result.search_id,
        result.found,
        result.new,
        result.notified,
        result.failed,
    )
    return asdict(result)


@celery_app.task(name="app.worker.tasks.enqueue_due_searches")
def enqueue_due_searches() -> int:
    """Beat tick: enqueue every search whose next_run_at is in the past.

    This is also the startup catch-up mechanism: any search left overdue while
    the system was down is picked up on the first tick. Because each run
    reschedules from *now*, a long downtime produces a single catch-up run per
    search, not one per missed interval.
    """
    with session_scope() as session:
        due_ids = [s.id for s in SearchRepository(session).due(utcnow())]

    for search_id in due_ids:
        run_search.delay(search_id)

    if due_ids:
        logger.info("enqueued %d due search(es): %s", len(due_ids), due_ids)
    return len(due_ids)
