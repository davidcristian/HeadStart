"""Tests for the pipeline auto-apply queueing hook."""

from __future__ import annotations

from app.scrapers.types import JobPosting
from app.services.apply import QueuedAutoApply
from app.services.pipeline_auto_apply import queue_auto_applies_for_new_jobs


class _StubApplyService:
    def __init__(self, results: dict[int, QueuedAutoApply | None]) -> None:
        self._results = results
        self.calls: list[tuple[int, int]] = []

    def enqueue_auto_apply_from_pipeline(self, user_id: int, job_id: int) -> QueuedAutoApply | None:
        self.calls.append((user_id, job_id))
        return self._results.get(job_id)


class _Row:
    def __init__(self, row_id: int) -> None:
        self.id = row_id


def _posting(external_id: str) -> JobPosting:
    return JobPosting(external_id=external_id, title="Job", company="ACME", url="")


def test_queue_auto_applies_appends_queued_and_skips_missing_rows() -> None:
    queued = QueuedAutoApply(application_log_id=10, user_id=1, job_id=100, cover_letter=None)
    apply_service = _StubApplyService({100: queued})
    postings = [_posting("a"), _posting("b")]
    # Only the first posting has a persisted seen-job row.
    seen_rows = {"a": _Row(100)}

    pending = queue_auto_applies_for_new_jobs(
        apply_service,  # type: ignore[arg-type]
        user_id=1,
        postings=postings,
        seen_rows=seen_rows,  # type: ignore[arg-type]
    )

    assert pending == [queued]
    # Posting "b" had no row, so it was skipped before enqueue.
    assert apply_service.calls == [(1, 100)]


def test_queue_auto_applies_drops_ineligible_jobs() -> None:
    apply_service = _StubApplyService({100: None})
    postings = [_posting("a")]
    seen_rows = {"a": _Row(100)}

    pending = queue_auto_applies_for_new_jobs(
        apply_service,  # type: ignore[arg-type]
        user_id=1,
        postings=postings,
        seen_rows=seen_rows,  # type: ignore[arg-type]
    )

    assert pending == []
    assert apply_service.calls == [(1, 100)]
