"""Ashby API response parsing helpers."""

from __future__ import annotations

from typing import Any


def extract_application_id(response: Any) -> str | None:
    """Submitted form instance id from a successful Ashby response."""
    if not isinstance(response, dict):
        return None
    results = response.get("results")
    if not isinstance(results, dict):
        return None
    instance = results.get("submittedFormInstance")
    if not isinstance(instance, dict):
        return None
    instance_id = instance.get("id")
    return str(instance_id) if instance_id is not None else None


def extract_blocked_message(response: Any) -> str | None:
    """Return a candidate-facing block message when Ashby rejects the submission."""
    if not isinstance(response, dict):
        return None
    results = response.get("results")
    if not isinstance(results, dict):
        return None
    form_messages = results.get("formMessages")
    if not isinstance(form_messages, dict) or not form_messages.get("blocked"):
        return None
    message = form_messages.get("blockMessageForCandidateHtml")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return "ashby blocked this application due to configured application limits"


def extract_error_message(response: dict[str, Any]) -> str:
    """Best-effort error string from an Ashby error response."""
    error_info = response.get("errorInfo")
    if isinstance(error_info, dict):
        message = error_info.get("message")
        if message:
            return str(message)
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        return "; ".join(str(item) for item in errors)
    return "ashby apply rejected the submission"
