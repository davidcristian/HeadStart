"""Tests for the Celery beat schedule builder."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.worker.schedule import beat_schedule


def test_beat_schedule_core_tasks_only_when_inbox_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    schedule = beat_schedule()

    assert set(schedule) == {"enqueue-due-searches", "flush-due-digests"}
    assert schedule["enqueue-due-searches"]["task"] == "app.worker.tasks.enqueue_due_searches"


def test_beat_schedule_includes_inbox_tasks_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    schedule = beat_schedule()

    assert "detect-ghosted-applications" in schedule
    assert "process-inbox-messages" in schedule
    assert "process-pending-replies" in schedule
    assert schedule["process-inbox-messages"]["task"] == "app.worker.tasks.process_inbox_messages"
