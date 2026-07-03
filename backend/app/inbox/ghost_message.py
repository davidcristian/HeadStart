"""Build self-sent ghost summary emails for stale applications."""

from __future__ import annotations

from datetime import datetime

from app.email_classifiers.labels import GHOST_HEADER_TYPE, GHOST_HEADER_VALUE, GHOST_SUBJECT_PREFIX
from app.inbox.types import OutboundMessage
from app.models.seen_job import SeenJob


def mailbox_self_address(*, imap_user: str, smtp_from: str) -> str:
    """Return the address used for self-sent ghost archive mail."""
    return (smtp_from or imap_user).strip()


def build_ghost_summary_message(*, job: SeenJob, mailbox_email: str) -> OutboundMessage:
    """Compose a ghost summary email with HeadStart archive markers."""
    company = job.company.strip() or "Unknown company"
    title = job.title.strip() or "Unknown role"
    subject = f"{GHOST_SUBJECT_PREFIX} No reply: {company} — {title}"
    body = _format_body(job=job, applied_at=job.applied_at)
    return OutboundMessage(
        to=[mailbox_email],
        subject=subject,
        body=body,
        extra_headers={
            GHOST_HEADER_TYPE: GHOST_HEADER_VALUE,
            "X-HeadStart-Job-Id": str(job.id),
        },
    )


def _format_body(*, job: SeenJob, applied_at: datetime | None) -> str:
    applied_label = applied_at.isoformat() if applied_at is not None else "unknown"
    lines = [
        "HeadStart recorded no recruiter reply for this application.",
        "",
        f"Company: {job.company or '—'}",
        f"Role: {job.title or '—'}",
        f"Location: {job.location or '—'}",
        f"Applied: {applied_label}",
    ]
    if job.url:
        lines.extend(["", f"Job link: {job.url}"])
    lines.extend(
        [
            "",
            "This is an automated ghost summary for your records.",
            "When it arrives in your inbox, HeadStart files it under HeadStart/Ghost.",
        ]
    )
    return "\n".join(lines)
