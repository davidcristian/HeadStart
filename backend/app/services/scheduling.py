"""Pure scheduling helpers (no I/O), shared by the API and the worker."""

from datetime import datetime, timedelta


def next_run_from(now: datetime, interval_seconds: int) -> datetime:
    """Compute the next run time as `now + interval`.

    Computing from *now* (rather than advancing the previous schedule N times) is
    what gives us safe catch-up: after downtime a search runs once and is then
    rescheduled, instead of firing once per missed interval.
    """
    return now + timedelta(seconds=max(interval_seconds, 1))
