"""Interview handoff when recruiter mail requests scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.inbox_classification import InboxClassification
from app.models.seen_job import SeenJob
from app.notifiers.types import DeliveryResult
from app.services.application_alerts import ApplicationAlertService
from app.services.applications import latest_live_attempt


@dataclass(frozen=True)
class InterviewHandoffResult:
    """Outcome of attempting interview handoff for one classification."""

    handed_off: bool
    alerts: tuple[DeliveryResult, ...] = ()


class InterviewHandoffService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.alerts = ApplicationAlertService(session)

    def maybe_handoff_from_classification(
        self,
        user_id: int,
        job: SeenJob,
        classification: InboxClassification,
    ) -> InterviewHandoffResult:
        """Mark interview pending and alert the user when scheduling mail arrives."""
        if classification.label != "interview_request":
            return InterviewHandoffResult(handed_off=False)
        if job.ghosted_at is not None:
            return InterviewHandoffResult(handed_off=False)
        if job.interview_pending_at is not None:
            return InterviewHandoffResult(handed_off=False)
        if not _is_active_application(job):
            return InterviewHandoffResult(handed_off=False)

        now = utcnow()
        job.interview_pending_at = now
        classification.payload = {
            **(classification.payload or {}),
            "interview_handoff": {
                "handed_off_at": now.isoformat(),
            },
        }
        alerts = self.alerts.notify_interview_handoff(
            user_id,
            job,
            email_subject=classification.subject,
        )
        self.session.flush()
        return InterviewHandoffResult(handed_off=True, alerts=tuple(alerts))


def _is_active_application(job: SeenJob) -> bool:
    """Return whether the job is in the live application pipeline."""
    if job.status in {"archived", "closed"}:
        return False
    if job.status == "applied":
        return True
    latest = latest_live_attempt(job.application_logs)
    return latest is not None and latest.status == "submitted"
