"""High-priority pipeline alerts via the user's notification targets."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.delivery_log import DeliveryLog
from app.models.notification_target import NotificationTarget
from app.models.seen_job import SeenJob
from app.models.user import User
from app.notifiers import NotifyContext, get_notifier
from app.notifiers.types import DeliveryResult
from app.repositories.targets import TargetRepository
from app.scrapers.types import JobPosting

logger = get_logger(__name__)

_HIGH_PRIORITY_TYPES = frozenset({"ntfy"})


class ApplicationAlertService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.targets = TargetRepository(session)

    def notify_ghost_recovery(
        self,
        user_id: int,
        job: SeenJob,
        *,
        label: str,
        email_subject: str | None = None,
    ) -> list[DeliveryResult]:
        """Push a high-priority alert when a ghosted application gets recruiter mail."""
        headline, summary = _ghost_recovery_copy(job, label=label)
        posting = self._alert_posting(
            job,
            external_id_prefix="ghost-recovery",
            title=email_subject or headline,
            summary=summary,
        )
        return self._send_alert(user_id, job, posting, log_context="ghost recovery")

    def notify_interview_handoff(
        self,
        user_id: int,
        job: SeenJob,
        *,
        email_subject: str | None = None,
    ) -> list[DeliveryResult]:
        """Push a high-priority alert when a recruiter requests an interview."""
        headline, summary = _interview_handoff_copy(job)
        posting = self._alert_posting(
            job,
            external_id_prefix="interview-handoff",
            title=email_subject or headline,
            summary=summary,
        )
        return self._send_alert(user_id, job, posting, log_context="interview handoff")

    def _send_alert(
        self,
        user_id: int,
        job: SeenJob,
        posting: JobPosting,
        *,
        log_context: str,
    ) -> list[DeliveryResult]:
        targets = self._resolve_targets(user_id, job)
        if not targets:
            return []

        results: list[DeliveryResult] = []
        owner = self.session.get(User, user_id)
        locale = owner.locale if owner is not None else None
        for target in targets:
            notifier = get_notifier(target.type)
            try:
                config = self._high_priority_config(target)
                sent = notifier.send(
                    NotifyContext(
                        target_type=target.type,
                        config=config,
                        locale=locale,
                    ),
                    [posting],
                )
                for res in sent:
                    self._record_delivery(job, target, res.status, res.error)
                results.extend(sent)
            except Exception as exc:
                logger.warning(
                    "%s alert failed target=%s user=%s: %s",
                    log_context,
                    target.id,
                    user_id,
                    exc,
                )
                self._record_delivery(job, target, "failed", str(exc))
                results.append(
                    DeliveryResult(
                        external_id=job.external_id,
                        status="failed",
                        error=str(exc),
                    )
                )
            finally:
                close = getattr(notifier, "close", None)
                if callable(close):
                    close()
        return results

    def _record_delivery(
        self, job: SeenJob, target: NotificationTarget, status: str, error: str | None
    ) -> None:
        """Audit an alert delivery like the pipeline/digest notification paths do."""
        self.session.add(
            DeliveryLog(seen_job_id=job.id, target_id=target.id, status=status, error=error)
        )

    def _resolve_targets(self, user_id: int, job: SeenJob) -> list[NotificationTarget]:
        """Prefer the search target; otherwise one stable default (never fan out)."""
        if job.search is not None and job.search.target_id is not None:
            target = self.targets.get(job.search.target_id, user_id)
            if target is not None:
                return [target]
        # No-target searches used to broadcast to every channel.
        fallback = self.targets.list_all(user_id)
        return fallback[:1]

    def _high_priority_config(self, target: NotificationTarget) -> dict[str, Any]:
        config = dict(target.config)
        if target.type in _HIGH_PRIORITY_TYPES:
            config["priority"] = "high"
        return config

    @staticmethod
    def _alert_posting(
        job: SeenJob,
        *,
        external_id_prefix: str,
        title: str,
        summary: str,
    ) -> JobPosting:
        return JobPosting(
            external_id=f"{external_id_prefix}-{job.id}",
            title=title,
            company=job.company,
            location=job.location,
            url=job.url,
            summary=summary,
        )


def _interview_handoff_copy(job: SeenJob) -> tuple[str, str]:
    company = job.company or "Employer"
    headline = f"Interview to schedule at {company}. Take over from here."
    summary = (
        f"{company} wants to schedule an interview for {job.title}. "
        "Check your inbox and calendar to pick a time."
    )
    return headline, summary


def _ghost_recovery_copy(job: SeenJob, *, label: str) -> tuple[str, str]:
    company = job.company or "Employer"
    if label == "interview_request":
        headline = f"Interview to schedule at {company}. Take over from here."
        summary = (
            f"{company} replied after you marked {job.title} as ghosted. "
            "They want to schedule an interview, so check your inbox and calendar."
        )
    elif label == "rejection":
        headline = f"{company} replied after you marked this ghosted"
        summary = (
            f"{company} sent a rejection for {job.title} after the ghost window. "
            "The application is no longer marked ghosted."
        )
    else:
        headline = f"{company} replied after you marked this ghosted"
        summary = (
            f"{company} responded about {job.title} after the ghost window. "
            "Review the thread and continue the conversation."
        )
    return headline, summary
