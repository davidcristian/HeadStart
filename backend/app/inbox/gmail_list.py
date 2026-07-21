"""Gmail INBOX id listing and internalDate probes for poll cursors.

`messages.list` returns ids only; uid ordering needs `internalDate` from a
separate get. Walk the newest-first listing from the oldest end and stop once
`limit` unpolled candidates are known so a busy inbox does not metadata-GET
every listed message.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.inbox.gmail_ids import gmail_message_uid, parse_internal_date, uid_to_min_received_at

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
INBOX_LABEL_ID = "INBOX"


def list_unpolled_candidates(
    headers: dict[str, str],
    *,
    since_uid: int | None,
    limit: int,
) -> list[tuple[int, str]]:
    """Return the oldest unpolled `(uid, gmail_id)` pairs up to `limit`."""
    ids = list_inbox_message_ids(headers, since_uid=since_uid, limit=limit)
    candidates: list[tuple[int, str]] = []
    for gmail_id in reversed(ids):
        received_at = message_received_at(headers, gmail_id)
        if received_at is None:
            continue
        uid = gmail_message_uid(gmail_id, received_at)
        if since_uid is not None and uid <= since_uid:
            continue
        candidates.append((uid, gmail_id))
        if len(candidates) >= limit:
            break
    candidates.sort(key=lambda row: row[0])
    return candidates


def list_inbox_message_ids(
    headers: dict[str, str],
    *,
    since_uid: int | None,
    limit: int,
) -> list[str]:
    """Page `messages.list` for INBOX ids only (no per-message metadata GETs)."""
    page_size = max(limit * 3, 100)
    max_pages = 20
    query: str | None = None
    if since_uid is not None:
        # Coarse server-side lower bound (with slack); the exact `uid <= since_uid`
        # skip in the caller dedupes the overlap, so a wider window never drops mail.
        after = int(uid_to_min_received_at(since_uid).timestamp()) - 60
        query = f"after:{max(after, 0)}"
    ids: list[str] = []
    seen: set[str] = set()
    page_token: str | None = None
    for _ in range(max_pages):
        params: dict[str, str | int] = {
            "labelIds": INBOX_LABEL_ID,
            "maxResults": page_size,
        }
        if query is not None:
            params["q"] = query
        if page_token is not None:
            params["pageToken"] = page_token
        response = httpx.get(
            f"{GMAIL_API_BASE}/users/me/messages",
            headers=headers,
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        for entry in payload.get("messages") or []:
            if not isinstance(entry, dict):
                continue
            gmail_id = entry.get("id")
            if not isinstance(gmail_id, str) or not gmail_id or gmail_id in seen:
                continue
            seen.add(gmail_id)
            ids.append(gmail_id)
        page_token = payload.get("nextPageToken")
        if not isinstance(page_token, str) or not page_token:
            break
    return ids


def message_received_at(headers: dict[str, str], gmail_id: str) -> datetime | None:
    """Fetch internalDate only (`format=minimal`) for uid ordering."""
    response = httpx.get(
        f"{GMAIL_API_BASE}/users/me/messages/{gmail_id}",
        headers=headers,
        params={"format": "minimal", "fields": "internalDate"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        return None
    return parse_internal_date(response.json().get("internalDate"))
