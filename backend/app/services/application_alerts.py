"""High-priority pipeline alerts via the user's notification targets."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.notification_target import NotificationTarget
from app.models.seen_job import SeenJob
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
        targets = self._resolve_targets(user_id, job)
        if not targets:
            return []

        posting = self._alert_posting(job, label=label, email_subject=email_subject)
        results: list[DeliveryResult] = []
        for target in targets:
            notifier = get_notifier(target.type)
            try:
                config = self._high_priority_config(target)
                sent = notifier.send(
                    NotifyContext(target_type=target.type, config=config),
                    [posting],
                )
                results.extend(sent)
            except Exception as exc:
                logger.warning(
                    "ghost recovery alert failed target=%s user=%s: %s",
                    target.id,
                    user_id,
                    exc,
                )
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

    def _resolve_targets(self, user_id: int, job: SeenJob) -> list[NotificationTarget]:
        if job.search is not None and job.search.target_id is not None:
            target = self.targets.get(job.search.target_id, user_id)
            if target is not None:
                return [target]
        return self.targets.list_all(user_id)

    def _high_priority_config(self, target: NotificationTarget) -> dict[str, Any]:
        config = dict(target.config)
        if target.type in _HIGH_PRIORITY_TYPES:
            config["priority"] = "high"
        return config

    @staticmethod
    def _alert_posting(
        job: SeenJob,
        *,
        label: str,
        email_subject: str | None,
    ) -> JobPosting:
        headline, summary = _ghost_recovery_copy(job, label=label)
        title = email_subject or headline
        return JobPosting(
            external_id=f"ghost-recovery-{job.id}",
            title=title,
            company=job.company,
            location=job.location,
            url=job.url,
            summary=summary,
        )


def _ghost_recovery_copy(job: SeenJob, *, label: str) -> tuple[str, str]:
    company = job.company or "Employer"
    if label == "interview_request":
        headline = f"Interview to schedule at {company} — take over from here"
        summary = (
            f"{company} replied after you marked {job.title} as ghosted. "
            "They want to schedule an interview — check your inbox and calendar."
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
