"""Match inbound email threads to known job applications."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.inbox.types import InboxMessage
from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.services.applications import latest_live_attempt

# Company substring alone scores +20; require title (+30), domain (+50), thread
# (+80), or company+title so a bare "Meta"/"Apple" mention cannot link (INB-18).
CONFIDENT_LINK_MIN_SCORE = 30


def email_domain(addr: str) -> str:
    """Return the lowercase domain part of an email address."""
    if "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[1].strip().lower()


def normalize_match_text(text: str) -> str:
    """Lowercase and collapse punctuation for fuzzy substring checks."""
    return re.sub(r"\W+", " ", text.lower()).strip()


def employer_domain_from_payload(log: ApplicationLog | None) -> str:
    """Read employer_domain from the latest application log payload."""
    if log is None or not log.payload:
        return ""
    raw = log.payload.get("employer_domain")
    return str(raw or "").strip().lower()


def normalize_message_id(value: str) -> str:
    """Normalize a Message-ID for comparison."""
    return value.strip()


def outbound_message_ids_from_log(log: ApplicationLog | None) -> set[str]:
    """Collect stored outbound Message-IDs from an application log payload."""
    if log is None or not log.payload:
        return set()
    raw = log.payload.get("outbound_message_ids") or []
    if not isinstance(raw, list):
        return set()
    return {normalize_message_id(str(item)) for item in raw if str(item).strip()}


def score_job_match(message: InboxMessage, job: SeenJob, log: ApplicationLog | None) -> int:
    """Score how likely an email belongs to one application."""
    score = 0
    employer_domain = employer_domain_from_payload(log)
    sender_domain = email_domain(message.from_addr)
    if (
        employer_domain
        and sender_domain
        and (sender_domain == employer_domain or sender_domain.endswith(f".{employer_domain}"))
    ):
        score += 50

    haystack = normalize_match_text(f"{message.subject} {message.body_text}")
    title = normalize_match_text(job.title)
    company = normalize_match_text(job.company)
    if title and len(title) > 3 and title in haystack:
        score += 30
    if company and len(company) > 2 and company in haystack:
        score += 20

    if message.in_reply_to:
        outbound_ids = outbound_message_ids_from_log(log)
        if normalize_message_id(message.in_reply_to) in outbound_ids:
            score += 80

    return score


def link_message_to_job(message: InboxMessage, jobs: list[SeenJob]) -> SeenJob | None:
    """Return the best matching application for an inbound email, if confident."""
    best_job: SeenJob | None = None
    best_score = 0
    for job in jobs:
        score = score_job_match(message, job, latest_live_attempt(job.application_logs))
        if score > best_score:
            best_score = score
            best_job = job
    if best_score >= CONFIDENT_LINK_MIN_SCORE:
        return best_job
    return None


def linked_application_context(job: SeenJob, log: ApplicationLog | None) -> dict[str, object]:
    """Build linked-application metadata for classification."""
    employer_domain = employer_domain_from_payload(log)
    if not employer_domain:
        employer_domain = urlparse(job.url).hostname or ""
        employer_domain = employer_domain.lower().removeprefix("www.")
    return {
        "seen_job_id": job.id,
        "job_title": job.title,
        "company": job.company,
        "employer_domain": employer_domain,
    }
