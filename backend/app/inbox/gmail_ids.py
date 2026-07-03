"""Time-ordered integer UIDs for Gmail messages (inbox poll cursors).

Gmail message ids are hex but NOT chronological, so parsing them as ints made the
oldest-first poll cursor skip later-arriving mail whose id sorted lower. Derive the
uid from the message's received time instead (like the Outlook/Fastmail adapters),
so `since_uid` advances monotonically in time. The raw Gmail id is carried on the
message headers for the move/route call rather than reversed out of the uid.
"""

from __future__ import annotations

import zlib
from datetime import UTC, datetime


def gmail_message_uid(gmail_id: str, received_at: datetime | None) -> int:
    """Map a Gmail message id + received time to a time-ordered integer uid."""
    if received_at is None:
        received_at = datetime.now(UTC)
    elif received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    # Milliseconds keep the uid < 2**63 so it fits a signed BigInteger column:
    # millis << 20 | 20-bit tail is ~62 bits through ~2255.
    millis = int(received_at.timestamp() * 1000)
    tail = zlib.crc32(gmail_id.strip().encode("utf-8")) & 0xFFFFF
    return millis * (1 << 20) | tail


def uid_to_min_received_at(since_uid: int) -> datetime:
    """Lower-bound received time encoded in a Gmail message uid."""
    millis = since_uid >> 20
    return datetime.fromtimestamp(millis / 1000, tz=UTC)


def parse_internal_date(value: object) -> datetime | None:
    """Parse a Gmail `internalDate` (epoch milliseconds as a string) to a datetime."""
    if not isinstance(value, str | int):
        return None
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis < 0:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=UTC)
