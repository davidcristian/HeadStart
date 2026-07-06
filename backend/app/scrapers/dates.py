"""Lenient date parsing for untrusted scraper payloads."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_iso8601(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp from untrusted upstream JSON.

    Returns ``None`` for missing, non-string, or malformed values so one bad
    date can't abort an entire scrape.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_epoch_seconds(value: object) -> datetime | None:
    """Parse a Unix epoch in seconds from untrusted upstream JSON.

    ``datetime.fromtimestamp`` raises ``OverflowError``/``OSError`` (not only
    ``ValueError``) on out-of-range values; catch those so one hostile epoch
    cannot abort the whole scrape page.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def parse_epoch_millis(value: object) -> datetime | None:
    """Parse a Unix epoch in milliseconds from untrusted upstream JSON."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
