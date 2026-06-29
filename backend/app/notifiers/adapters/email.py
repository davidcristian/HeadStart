"""Email notifier.

Sends one plain-text email per new job using the app-wide SMTP settings
(SMTP_* env vars). Target config only needs the recipient address.

Target config:
    {
      "to": "you@example.com"   # required
    }
"""

import smtplib

from app.core.email import SmtpNotConfiguredError, send_email
from app.core.logging import get_logger
from app.notifiers.base import Notifier, register_notifier
from app.notifiers.digest_format import digest_plain_body, digest_title
from app.notifiers.types import DeliveryResult, NotifyContext
from app.scrapers.types import JobPosting

logger = get_logger(__name__)


@register_notifier("email")
class EmailNotifier(Notifier):
    """Send new jobs as plain-text emails."""

    def send(self, ctx: NotifyContext, jobs: list[JobPosting]) -> list[DeliveryResult]:
        to = ctx.config.get("to")
        if not to or not str(to).strip():
            raise ValueError("email target requires config.to")

        recipient = str(to).strip()
        if ctx.digest:
            return self._send_digest(recipient, ctx, jobs)

        results: list[DeliveryResult] = []
        for job in jobs:
            results.append(self._send_one(recipient, job))
        return results

    def _send_digest(
        self, recipient: str, ctx: NotifyContext, jobs: list[JobPosting]
    ) -> list[DeliveryResult]:
        if not jobs:
            return []
        subject = digest_title(len(jobs), ctx.search_name)
        body = digest_plain_body(jobs)
        try:
            send_email(to=recipient, subject=subject, body=body)
            return [DeliveryResult(external_id=job.external_id, status="sent") for job in jobs]
        except SmtpNotConfiguredError as exc:
            logger.warning("email digest send skipped: %s", exc)
            return [
                DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))
                for job in jobs
            ]
        except smtplib.SMTPException as exc:
            logger.warning("email digest send failed: %s", exc)
            return [
                DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))
                for job in jobs
            ]

    def _send_one(self, recipient: str, job: JobPosting) -> DeliveryResult:
        subject = self._subject(job)
        body = self._body(job)
        try:
            send_email(to=recipient, subject=subject, body=body)
            return DeliveryResult(external_id=job.external_id, status="sent")
        except SmtpNotConfiguredError as exc:
            logger.warning("email send skipped for %s: %s", job.external_id, exc)
            return DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))
        except smtplib.SMTPException as exc:
            logger.warning("email send failed for %s: %s", job.external_id, exc)
            return DeliveryResult(external_id=job.external_id, status="failed", error=str(exc))

    @staticmethod
    def _subject(job: JobPosting) -> str:
        return f"{job.title} @ {job.company}" if job.company else job.title

    @staticmethod
    def _body(job: JobPosting) -> str:
        lines = [job.title]
        if job.summary:
            lines.append(f"Why this matches: {job.summary}")
        if job.company:
            lines.append(f"Company: {job.company}")
        if job.location:
            lines.append(f"Location: {job.location}")
        if job.url:
            lines.append(f"Apply: {job.url}")
        return "\n".join(lines)
