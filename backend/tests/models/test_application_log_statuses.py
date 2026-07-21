"""Regression tests for ApplicationLog status vocabulary."""

from __future__ import annotations

import inspect

from app.models import application_log as application_log_module
from app.models.application_log import (
    APPLICATION_LOG_IN_FLIGHT_STATUSES,
    APPLICATION_LOG_STATUSES,
)


def test_application_log_statuses_include_in_flight_and_terminals() -> None:
    """Model comment / constant must list enqueue and claim statuses, not only terminals."""
    assert frozenset({"queued", "processing"}) == APPLICATION_LOG_IN_FLIGHT_STATUSES
    assert (
        frozenset({"queued", "processing", "submitted", "dry_run", "failed"})
        == APPLICATION_LOG_STATUSES
    )
    assert APPLICATION_LOG_IN_FLIGHT_STATUSES <= APPLICATION_LOG_STATUSES


def test_application_log_status_column_comment_lists_all_statuses() -> None:
    """Inline status comment must not omit queued/processing."""
    source = inspect.getsource(application_log_module)
    comment_line = next(
        line for line in source.splitlines() if "queued | processing | submitted" in line
    )
    for status in sorted(APPLICATION_LOG_STATUSES):
        assert status in comment_line
