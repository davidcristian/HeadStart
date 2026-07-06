"""Topic blocklist and rate-limit helpers for autonomous recruiter replies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

SENSITIVE_TOPIC_PATTERNS: Final[list[tuple[str, re.Pattern[str]]]] = [
    ("lawsuit", re.compile(r"\blawsuits?\b", re.IGNORECASE)),
    ("litigation", re.compile(r"\blitigation\b", re.IGNORECASE)),
    ("attorney", re.compile(r"\battorneys?\b", re.IGNORECASE)),
    ("legal_action", re.compile(r"\blegal action\b", re.IGNORECASE)),
    ("discrimination", re.compile(r"\bdiscriminat(?:ion|ory)\b", re.IGNORECASE)),
    ("harassment", re.compile(r"\bharass(?:ment|ing)\b", re.IGNORECASE)),
    ("hostile_workplace", re.compile(r"\bhostile work(?:place| environment)\b", re.IGNORECASE)),
    ("wrongful_termination", re.compile(r"\bwrongful terminat(?:ion|e)\b", re.IGNORECASE)),
    ("severance", re.compile(r"\bseverance\b", re.IGNORECASE)),
    ("eeoc", re.compile(r"\bEEOC\b")),
    ("grievance", re.compile(r"\bgrievance\b", re.IGNORECASE)),
    ("whistleblower", re.compile(r"\bwhistleblow(?:er|ing)\b", re.IGNORECASE)),
    ("settlement", re.compile(r"\bsettlement offer\b", re.IGNORECASE)),
    ("nda_breach", re.compile(r"\bNDA breach\b", re.IGNORECASE)),
    ("non_compete", re.compile(r"\bnon[- ]compete\b", re.IGNORECASE)),
    ("hr_investigation", re.compile(r"\bHR investigation\b", re.IGNORECASE)),
    # Optional apostrophe + flexible whitespace so "workers compensation" and
    # "workers' compensation" both match (INB-04: `[' ]` + literal space needed two chars).
    ("workers_comp", re.compile(r"\bworkers['’]?\s*compensation\b", re.IGNORECASE)),
]


@dataclass(frozen=True)
class TopicBlockResult:
    """Outcome when a reply is blocked by the topic filter."""

    matched_topics: tuple[str, ...]
    reason: str


def find_sensitive_topics(*texts: str) -> list[str]:
    """Return topic labels matched in the combined message text."""
    combined = "\n".join(text.strip() for text in texts if text and text.strip())
    if not combined:
        return []
    matched: list[str] = []
    for label, pattern in SENSITIVE_TOPIC_PATTERNS:
        if pattern.search(combined):
            matched.append(label)
    return matched


def check_topic_blocklist(
    *,
    inbound_subject: str = "",
    inbound_body: str = "",
    draft_subject: str = "",
    draft_body: str = "",
) -> TopicBlockResult | None:
    """Return a block result when legal/HR-sensitive topics are detected."""
    matched = find_sensitive_topics(inbound_subject, inbound_body, draft_subject, draft_body)
    if not matched:
        return None
    labels = ", ".join(matched)
    return TopicBlockResult(
        matched_topics=tuple(matched),
        reason=f"Auto-reply blocked: sensitive topic(s) detected ({labels}).",
    )
