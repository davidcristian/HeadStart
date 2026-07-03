"""Recover ghosted applications when recruiter mail arrives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.email_classifiers.labels import GHOST_RECOVERY_SIGNAL_LABELS
from app.models.base import utcnow
from app.models.inbox_classification import InboxClassification
from app.models.seen_job import SeenJob
from app.notifiers.types import DeliveryResult
from app.services.application_alerts import ApplicationAlertService


@dataclass(frozen=True)
class GhostRecoveryResult:
    """Outcome of attempting ghost recovery for one classification."""

    recovered: bool
    pipeline_stage: str | None = None
    alerts: tuple[DeliveryResult, ...] = ()


class GhostRecoveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.alerts = ApplicationAlertService(session)

    def maybe_recover_from_classification(
        self,
        user_id: int,
        job: SeenJob,
        classification: InboxClassification,
    ) -> GhostRecoveryResult:
        """Clear ghost state and alert the user when recruiter mail revives a ghosted job."""
        if job.ghosted_at is None:
            return GhostRecoveryResult(recovered=False)
        if classification.label not in GHOST_RECOVERY_SIGNAL_LABELS:
            return GhostRecoveryResult(recovered=False)

        now = utcnow()
        previous_ghosted_at = job.ghosted_at
        stage = self._apply_recovery(job, label=classification.label, now=now)
        classification.payload = {
            **(classification.payload or {}),
            "ghost_recovery": {
                "recovered_at": now.isoformat(),
                "previous_ghosted_at": (
                    previous_ghosted_at.isoformat() if previous_ghosted_at else None
                ),
                "pipeline_stage": stage,
            },
        }
        alerts = self.alerts.notify_ghost_recovery(
            user_id,
            job,
            label=classification.label,
            email_subject=classification.subject,
        )
        self.session.flush()
        return GhostRecoveryResult(
            recovered=True,
            pipeline_stage=stage,
            alerts=tuple(alerts),
        )

    @staticmethod
    def _apply_recovery(job: SeenJob, *, label: str, now: datetime) -> str:
        job.ghost_recovered_at = now
        job.ghosted_at = None
        job.interview_pending_at = None
        job.recruiter_rejection_at = None

        if label == "interview_request":
            job.interview_pending_at = now
            return "interview_pending"
        if label == "rejection":
            job.recruiter_rejection_at = now
            return "rejected"
        return "awaiting_reply"
