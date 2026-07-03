"""Helpers for parsing raw RFC 822 messages into InboxMessage."""

from __future__ import annotations

import email
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime

from app.inbox.types import InboxMessage


def decode_mime_header(value: str | None) -> str:
    """Decode a MIME-encoded header to a plain string."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (email.errors.HeaderParseError, UnicodeError, ValueError):
        return value


def extract_body_text(message: Message) -> str:
    """Return the best-effort plain-text body from a parsed email."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    if isinstance(payload, str):
        return payload
    return ""


def parse_rfc822(uid: int, raw_bytes: bytes) -> InboxMessage:
    """Parse a fetched RFC 822 message into a normalized InboxMessage."""
    message = email.message_from_bytes(raw_bytes)
    from_addrs = [addr for _, addr in getaddresses([message.get("From", "")]) if addr]
    to_addrs = [addr for _, addr in getaddresses([message.get("To", "")]) if addr]
    received_at: datetime | None = None
    date_header = message.get("Date")
    if date_header:
        try:
            received_at = parsedate_to_datetime(date_header)
        except (TypeError, ValueError, OverflowError):
            received_at = None
    headers = {
        key: decode_mime_header(value)
        for key, value in message.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    return InboxMessage(
        uid=uid,
        message_id=message.get("Message-ID"),
        in_reply_to=message.get("In-Reply-To"),
        references=message.get("References"),
        from_addr=from_addrs[0] if from_addrs else "",
        to_addrs=to_addrs,
        subject=decode_mime_header(message.get("Subject")),
        body_text=extract_body_text(message),
        received_at=received_at,
        raw_headers=headers,
    )
