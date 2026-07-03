"""Convert JMAP Email objects into normalized inbox messages."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Any

from app.inbox.types import InboxMessage

JMAP_EMAIL_ID_HEADER = "x-headstart-jmap-id"


def jmap_email_to_inbox_message(email: dict[str, Any], uid: int) -> InboxMessage:
    """Convert a JMAP Email/get object into a normalized InboxMessage."""
    email_id = email.get("id")
    headers = _headers_map(email.get("headers"))
    from_addr = _first_address(email.get("from")) or _header_value(headers, "From")
    to_addrs = _address_list(email.get("to")) or _parse_address_header(headers.get("To", ""))
    received_at = _parse_received_at(email.get("receivedAt"))
    references = _references_value(email.get("references")) or _header_value(headers, "References")
    return InboxMessage(
        uid=uid,
        message_id=_header_value(headers, "Message-ID") or email.get("messageId"),
        in_reply_to=email.get("inReplyTo") or _header_value(headers, "In-Reply-To"),
        references=references,
        from_addr=from_addr,
        to_addrs=to_addrs,
        subject=_decode_subject(email.get("subject")) or _header_value(headers, "Subject"),
        body_text=_extract_body_text(email),
        received_at=received_at,
        raw_headers={
            **headers,
            JMAP_EMAIL_ID_HEADER: email_id if isinstance(email_id, str) else "",
        },
    )


def _headers_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, list):
        return {}
    headers: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if isinstance(name, str) and isinstance(value, str):
            headers[name] = value
    return headers


def _header_value(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _first_address(raw: Any) -> str:
    addresses = _address_list(raw)
    return addresses[0] if addresses else ""


def _address_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    addresses: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        email = item.get("email")
        if isinstance(email, str) and email:
            addresses.append(email)
    return addresses


def _parse_address_header(value: str) -> list[str]:
    if not value:
        return []
    return [addr for _, addr in [parseaddr(value)] if addr]


def _references_value(raw: Any) -> str | None:
    if isinstance(raw, list):
        refs = [item for item in raw if isinstance(item, str) and item]
        return " ".join(refs) if refs else None
    if isinstance(raw, str) and raw:
        return raw
    return None


def _decode_subject(raw: Any) -> str:
    return raw if isinstance(raw, str) else ""


def _parse_received_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _extract_body_text(email: dict[str, Any]) -> str:
    body_values = email.get("bodyValues")
    if isinstance(body_values, dict):
        for part in email.get("textBody") or []:
            if not isinstance(part, dict):
                continue
            part_id = part.get("partId")
            if not isinstance(part_id, str):
                continue
            entry = body_values.get(part_id)
            if isinstance(entry, dict):
                value = entry.get("value")
                if isinstance(value, str):
                    return value
        for entry in body_values.values():
            if isinstance(entry, dict):
                value = entry.get("value")
                if isinstance(value, str) and value:
                    return value
    return ""
