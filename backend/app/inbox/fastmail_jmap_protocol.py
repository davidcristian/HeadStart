"""JMAP response parsing helpers for Fastmail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

JMAP_CORE = "urn:ietf:params:jmap:core"
JMAP_MAIL = "urn:ietf:params:jmap:mail"
JMAP_SUBMISSION = "urn:ietf:params:jmap:submission"
FASTMAIL_SESSION_URL = "https://api.fastmail.com/jmap/session"
INBOX_ROLE = "inbox"


@dataclass(frozen=True)
class JmapSession:
    """Resolved Fastmail JMAP session metadata."""

    api_url: str
    account_id: str
    username: str


def response_list(responses: list[list[Any]], method_name: str) -> list[dict[str, Any]]:
    for response in responses:
        if len(response) < 2 or response[0] != method_name:
            continue
        body = response[1]
        if not isinstance(body, dict):
            return []
        rows = body.get("list")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def response_ids(responses: list[list[Any]], method_name: str) -> list[str]:
    for response in responses:
        if len(response) < 2 or response[0] != method_name:
            continue
        body = response[1]
        if not isinstance(body, dict):
            return []
        ids = body.get("ids")
        if isinstance(ids, list):
            return [item for item in ids if isinstance(item, str)]
    return []


def response_created(responses: list[list[Any]], method_name: str) -> dict[str, Any]:
    for response in responses:
        if len(response) < 2 or response[0] != method_name:
            continue
        body = response[1]
        if not isinstance(body, dict):
            return {}
        created = body.get("created")
        if isinstance(created, dict):
            for value in created.values():
                if isinstance(value, dict):
                    return value
    return {}
