"""Stable integer UIDs for Microsoft Graph message ids (inbox poll cursors)."""

from __future__ import annotations

import zlib
from datetime import UTC, datetime


def outlook_message_uid(graph_id: str, received_at: datetime | None) -> int:
    """Map a Graph message id to a mostly time-ordered integer uid."""
    if received_at is None:
        received_at = datetime.now(UTC)
    elif received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    micros = int(received_at.timestamp() * 1_000_000)
    tail = zlib.crc32(graph_id.encode("utf-8")) & 0xFFFFF
    return micros * (1 << 20) | tail


def uid_to_min_received_at(since_uid: int) -> datetime:
    """Lower-bound received time encoded in an Outlook message uid."""
    micros = since_uid >> 20
    return datetime.fromtimestamp(micros / 1_000_000, tz=UTC)
