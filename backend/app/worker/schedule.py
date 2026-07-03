"""Celery beat schedule definition.

A single periodic task ticks every `SCHEDULER_TICK_SECONDS` and enqueues any
searches that are due. Keeping the cadence here (not in code scattered around)
makes the scheduler easy to reason about.
"""

from app.core.config import settings


def beat_schedule() -> dict[str, dict[str, object]]:
    tick = float(settings.scheduler_tick_seconds)
    schedule: dict[str, dict[str, object]] = {
        "enqueue-due-searches": {
            "task": "app.worker.tasks.enqueue_due_searches",
            "schedule": tick,
        },
        "flush-due-digests": {
            "task": "app.worker.tasks.flush_due_digests",
            "schedule": tick,
        },
    }
    if settings.inbox_agent_enabled:
        schedule["detect-ghosted-applications"] = {
            "task": "app.worker.tasks.detect_ghosted_applications",
            "schedule": float(settings.inbox_ghost_check_interval_seconds),
        }
    return schedule
