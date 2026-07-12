"""Redact secrets from httpx error text before log/persist."""

from __future__ import annotations

_REDACTED = "[REDACTED]"


def safe_http_error(exc: BaseException, *secrets: str) -> str:
    """Strip known secrets (webhook URLs, tokens, topics) from exception text."""
    text = str(exc)
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, _REDACTED)
    return text
