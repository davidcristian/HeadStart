"""Heuristic email classifier — offline default."""

from __future__ import annotations

import re

from app.email_classifiers.base import EmailClassifier, register_email_classifier
from app.email_classifiers.labels import (
    GHOST_HEADER_TYPE,
    GHOST_HEADER_VALUE,
    GHOST_SUBJECT_PREFIX,
)
from app.email_classifiers.sanitize import looks_like_prompt_injection
from app.email_classifiers.types import EmailClassificationResult, EmailClassifyContext

_REJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"unfortunately", re.I),
    re.compile(r"not\s+(moving|proceeding)\s+forward", re.I),
    re.compile(r"other\s+candidates", re.I),
    re.compile(r"position\s+has\s+been\s+filled", re.I),
    re.compile(r"regret\s+to\s+inform", re.I),
    re.compile(r"will\s+not\s+be\s+moving\s+forward", re.I),
)

_INTERVIEW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"calendly", re.I),
    re.compile(r"schedule\s+(a\s+)?(call|interview|chat|meeting)", re.I),
    re.compile(r"phone\s+screen", re.I),
    re.compile(r"video\s+interview", re.I),
    re.compile(r"set\s+up\s+(a\s+)?(time|call)", re.I),
    re.compile(r"interview\s+(with|for)", re.I),
)

_FOLLOW_UP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"work\s+authorization", re.I),
    re.compile(r"salary\s+expectations?", re.I),
    re.compile(r"when\s+can\s+you\s+start", re.I),
    re.compile(r"availability", re.I),
    re.compile(r"\?"),
)


@register_email_classifier("heuristic")
class HeuristicEmailClassifier(EmailClassifier):
    """Classify recruiter email with keyword and header rules."""

    def __init__(self, *, settings: object | None = None) -> None:
        pass

    def classify(self, ctx: EmailClassifyContext) -> EmailClassificationResult:
        return _classify(ctx)


def _classify(ctx: EmailClassifyContext) -> EmailClassificationResult:
    message = ctx.message
    haystack = f"{message.subject}\n{message.body_text}"

    if _is_self_ghost_archive(ctx):
        return EmailClassificationResult(
            label="self_ghost_archive",
            confidence=0.95,
            reason="Message matches HeadStart ghost-archive markers.",
        )

    if looks_like_prompt_injection(haystack):
        return EmailClassificationResult(
            label="out_of_scope",
            confidence=0.9,
            reason="Body contains instruction-injection patterns.",
        )

    if _matches_any(_REJECTION_PATTERNS, haystack):
        return EmailClassificationResult(
            label="rejection",
            confidence=0.85,
            reason="Rejection language detected in subject or body.",
        )

    if _matches_any(_INTERVIEW_PATTERNS, haystack):
        return EmailClassificationResult(
            label="interview_request",
            confidence=0.85,
            reason="Interview or scheduling language detected.",
        )

    if _matches_any(_FOLLOW_UP_PATTERNS, haystack):
        return EmailClassificationResult(
            label="follow_up",
            confidence=0.75,
            reason="Recruiter follow-up question detected.",
        )

    return EmailClassificationResult(
        label="general",
        confidence=0.6,
        reason="General recruiter correspondence.",
    )


def _is_self_ghost_archive(ctx: EmailClassifyContext) -> bool:
    message = ctx.message
    headers = {key.lower(): value for key, value in message.raw_headers.items()}
    if headers.get(GHOST_HEADER_TYPE.lower(), "").strip().lower() == GHOST_HEADER_VALUE:
        return True
    if message.subject.strip().startswith(GHOST_SUBJECT_PREFIX):
        return True
    mailbox = ctx.mailbox_user_email.strip().lower()
    if not mailbox:
        return False
    from_addr = message.from_addr.strip().lower()
    to_addrs = [addr.strip().lower() for addr in message.to_addrs]
    return from_addr == mailbox and mailbox in to_addrs


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)
