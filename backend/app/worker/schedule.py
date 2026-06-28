"""Celery beat schedule definition.

A single periodic task ticks every `SCHEDULER_TICK_SECONDS` and enqueues any
searches that are due. Keeping the cadence here (not in code scattered around)
makes the scheduler easy to reason about.
"""

from app.core.config import settings


def beat_schedule() -> dict[str, dict[str, object]]:
    tick = float(settings.scheduler_tick_seconds)
    return {
        "enqueue-due-searches": {
            "task": "app.worker.tasks.enqueue_due_searches",
            "schedule": tick,
        },
        "flush-due-digests": {
            "task": "app.worker.tasks.flush_due_digests",
            "schedule": tick,
        },
    }
