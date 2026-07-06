"""Queue and complete async manual search pipeline runs (API-02)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.base import utcnow
from app.models.search_run import SearchRun
from app.repositories.search_runs import SearchRunRepository
from app.repositories.searches import SearchRepository
from app.schemas.search_run import SearchRunRead
from app.services.apply import QueuedAutoApply
from app.services.pipeline import PipelineService

logger = get_logger(__name__)

_RESULT_KEYS = (
    "found",
    "new",
    "notified",
    "failed",
    "skipped",
    "filtered",
    "queued",
    "closed",
)


class SearchRunService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SearchRunRepository(session)
        self.searches = SearchRepository(session)

    def enqueue(self, user_id: int, search_id: int) -> SearchRunRead:
        """Validate ownership and queue a manual pipeline run for the worker."""
        search = self.searches.get(search_id, user_id)
        if search is None:
            raise NotFoundError(f"Search {search_id} not found")
        now = utcnow()
        row = SearchRun(
            user_id=user_id,
            search_id=search_id,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        self.repo.add(row)
        return SearchRunRead.from_row(row)

    def get_for_user(self, user_id: int, run_id: int) -> SearchRunRead:
        """Return one search run scoped to the authenticated user."""
        row = self.repo.get_for_user(run_id, user_id)
        if row is None:
            raise NotFoundError(f"Search run {run_id} not found")
        return SearchRunRead.from_row(row)

    def claim(self, run_id: int) -> SearchRun | None:
        """Lease a queued run (queued → processing) before scrape/LLM work."""
        row = self.repo.get(run_id)
        if row is None or row.status != "queued":
            return None
        row.status = "processing"
        row.updated_at = utcnow()
        self.session.flush()
        return row

    def complete(self, run_id: int, user_id: int, search_id: int) -> list[QueuedAutoApply]:
        """Run the pipeline, store counts, and return pending auto-applies."""
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Search run {run_id} not found")
        if row.user_id != user_id or row.search_id != search_id:
            raise NotFoundError(f"Search run {run_id} not found")
        if row.status != "processing":
            return []
        result = PipelineService(self.session).run(search_id)
        payload: dict[str, Any] = {key: getattr(result, key) for key in _RESULT_KEYS}
        row.result = payload
        row.error = result.error
        row.status = "failed" if result.error else "ready"
        row.updated_at = utcnow()
        self.session.flush()
        if result.error:
            logger.warning(
                "search_run failed id=%s search=%s user=%s: %s",
                run_id,
                search_id,
                user_id,
                result.error,
            )
        return list(result.pending_auto_applies)
