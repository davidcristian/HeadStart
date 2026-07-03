"""Pre-LLM sanitization for inbound recruiter email."""

from __future__ import annotations

import html
import re

from app.inbox.types import InboxMessage

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(above|prior)\s+(instructions|prompt)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"jailbreak", re.I),
)


def sanitize_message_body(body: str, *, max_chars: int) -> str:
    """Strip HTML, collapse whitespace, and cap body length."""
    text = html.unescape(body or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars > 0 and len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def looks_like_prompt_injection(text: str) -> bool:
    """Return True when the body contains obvious instruction-injection patterns."""
    if not text.strip():
        return False
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def prepare_message(message: InboxMessage, *, max_chars: int) -> InboxMessage:
    """Return a copy of the message with a sanitized body for classification."""
    sanitized_body = sanitize_message_body(message.body_text, max_chars=max_chars)
    return message.model_copy(update={"body_text": sanitized_body})
