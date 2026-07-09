"""Shared post-2xx error-body checks for hosted Easy Apply submits.

Indeed smartapply and LinkedIn Voyager (and siblings like Greenhouse /
SmartRecruiters) can return HTTP 2xx whose JSON body still reports failure.
Adapters call these helpers before treating a response as ``submitted``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def response_has_error(
    response: Any,
    *,
    extract_application_id: Callable[[Any], str | None],
) -> bool:
    """True when a 2xx JSON body carries an explicit failure envelope."""
    if not isinstance(response, dict):
        return False
    if response.get("success") is False or bool(response.get("error") or response.get("errors")):
        return True
    # Soft-fail envelope: message present but no application id (SmartRecruiters).
    return bool(response.get("message")) and extract_application_id(response) is None


def extract_error_message(response: Any, *, default: str) -> str:
    """Best-effort human-readable string from a hosted-submit error body."""
    if not isinstance(response, dict):
        return default
    error = response.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        parts = [
            str(item.get("message") or item) if isinstance(item, dict) else str(item)
            for item in errors
        ]
        return "; ".join(parts)
    if isinstance(errors, str) and errors.strip():
        return errors.strip()
    message = response.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return default
