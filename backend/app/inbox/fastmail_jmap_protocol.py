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


_SET_FAILURE_KEYS = ("notCreated", "notUpdated", "notDestroyed")


def raise_on_jmap_method_errors(responses: list[list[Any]]) -> None:
    """Raise when JMAP reports a method-level error inside an HTTP 200 body.

    RFC 8620 §3.6 returns per-method failures as ``["error", …]`` rows or as
    non-empty ``notCreated`` / ``notUpdated`` / ``notDestroyed`` maps on ``*/set``
    responses. Neither shape is caught by ``raise_for_status``.
    """
    for response in responses:
        if not isinstance(response, list) or len(response) < 2:
            continue
        name = response[0]
        body = response[1]
        if name == "error":
            raise ValueError(_jmap_error_message(body, fallback="JMAP method error"))
        if not isinstance(body, dict):
            continue
        for key in _SET_FAILURE_KEYS:
            failures = body.get(key)
            if isinstance(failures, dict) and failures:
                raise ValueError(
                    _jmap_set_failure_message(name, key, failures),
                )


def _jmap_error_message(body: Any, *, fallback: str) -> str:
    if not isinstance(body, dict):
        return fallback
    description = body.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    error_type = body.get("type")
    if isinstance(error_type, str) and error_type.strip():
        return f"JMAP error: {error_type.strip()}"
    return fallback


def _jmap_set_failure_message(
    method_name: Any,
    failure_key: str,
    failures: dict[str, Any],
) -> str:
    label = method_name if isinstance(method_name, str) else "JMAP"
    first_key, first_value = next(iter(failures.items()))
    detail = _jmap_error_message(first_value, fallback=str(first_value))
    return f"JMAP {label} {failure_key} for {first_key}: {detail}"
