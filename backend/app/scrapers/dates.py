"""Lenient date parsing for untrusted scraper payloads."""

from __future__ import annotations

from datetime import datetime


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
