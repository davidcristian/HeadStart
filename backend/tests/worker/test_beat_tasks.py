"""Tests for the thin Celery beat tasks (glue over services)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.worker import tasks
from tests.worker.pipeline_helpers import make_search


@pytest.fixture
def worker_scope(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    @contextmanager
    def _scope() -> Iterator[Session]:
        yield db_session
        db_session.commit()

    monkeypatch.setattr(tasks, "session_scope", _scope)
    return db_session


def test_enqueue_due_searches_dispatches_and_counts(worker_scope: Session) -> None:
    from datetime import timedelta

    from app.models.base import utcnow

    search = make_search(worker_scope, next_run_at=utcnow() - timedelta(seconds=5))
    with patch.object(tasks.run_search, "delay") as mock_delay:
        count = tasks.enqueue_due_searches()

    assert count == 1
    mock_delay.assert_called_once_with(search.id)


def test_enqueue_due_searches_no_due(worker_scope: Session) -> None:
    from datetime import timedelta

    from app.models.base import utcnow

    make_search(worker_scope, next_run_at=utcnow() + timedelta(seconds=300))
    with patch.object(tasks.run_search, "delay") as mock_delay:
        count = tasks.enqueue_due_searches()

    assert count == 0
    mock_delay.assert_not_called()


def test_flush_due_digests_logs_when_flushed(worker_scope: Session) -> None:
    with patch.object(tasks.DigestService, "flush_due", return_value=2) as mock_flush:
        assert tasks.flush_due_digests() == 2
    mock_flush.assert_called_once()


def test_flush_due_digests_zero(worker_scope: Session) -> None:
    with patch.object(tasks.DigestService, "flush_due", return_value=0):
        assert tasks.flush_due_digests() == 0


def test_detect_ghosted_applications(worker_scope: Session) -> None:
    result = MagicMock(checked=4, ghosted=1, skipped=2, failed=0)
    with patch.object(tasks.GhostDetectionService, "process_due", return_value=result):
        payload = tasks.detect_ghosted_applications()
    assert payload == {"checked": 4, "ghosted": 1, "skipped": 2, "failed": 0}


def test_process_inbox_messages(worker_scope: Session) -> None:
    result = MagicMock(users=1, fetched=3, classified=2, skipped=1, ignored=0, failed=0)
    with patch.object(tasks.InboxOrchestrationService, "process_due", return_value=result):
        payload = tasks.process_inbox_messages()
    assert payload == {
        "users": 1,
        "fetched": 3,
        "classified": 2,
        "skipped": 1,
        "ignored": 0,
        "failed": 0,
    }


def test_process_pending_replies(worker_scope: Session) -> None:
    result = MagicMock(checked=5, sent=2, failed=0, skipped=1, blocked=0)
    with patch.object(tasks.PendingReplyService, "process_due", return_value=result):
        payload = tasks.process_pending_replies()
    assert payload == {
        "checked": 5,
        "sent": 2,
        "failed": 0,
        "skipped": 1,
        "blocked": 0,
    }
