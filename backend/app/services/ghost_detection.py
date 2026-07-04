"""Detect stale applications and send self-archived ghost summary emails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.inbox.ghost_message import build_ghost_summary_message
from app.inbox.mailbox_email import mailbox_email_from_context
from app.models.base import utcnow
from app.models.seen_job import SeenJob
from app.repositories.ghost_detection import GhostDetectionRepository
from app.services.applications import latest_live_attempt
from app.services.inbox import InboxService

logger = get_logger(__name__)


@dataclass(frozen=True)
class GhostDetectionResult:
    """Outcome of one ghost-detection pass."""

    checked: int
    ghosted: int
    skipped: int
    failed: int


class GhostDetectionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = GhostDetectionRepository(session)
        self.inbox = InboxService(session)

    def process_due(self, *, now: datetime | None = None) -> GhostDetectionResult:
        """Find stale applications and ghost them when inbox automation is enabled.

        Per-item isolation (SVC-06): a raise from one job (token refresh, SMTP,
        validation) is logged and counted as failed so other stale applications
        still process; each successful ghost commits immediately so a later
        failure cannot roll back already-set ``ghosted_at`` via ``session_scope``.
        """
        if not settings.inbox_agent_enabled:
            return GhostDetectionResult(checked=0, ghosted=0, skipped=0, failed=0)

        current = now or utcnow()
        cutoff = current - timedelta(days=settings.inbox_ghost_window_days)
        checked = 0
        ghosted = 0
        skipped = 0
        failed = 0

        for user_id, job in self.repo.list_stale_applications(cutoff=cutoff):
            checked += 1
            try:
                outcome = self._process_job(user_id, job, now=current)
                if outcome == "ghosted":
                    self.session.commit()
                    ghosted += 1
                elif outcome == "failed":
                    failed += 1
                else:
                    skipped += 1
            except Exception:
                self.session.rollback()
                logger.exception(
                    "ghost detection failed for job %s user %s; continuing",
                    job.id,
                    user_id,
                )
                failed += 1

        if ghosted or failed:
            logger.info(
                "ghost detection: checked=%d ghosted=%d skipped=%d failed=%d",
                checked,
                ghosted,
                skipped,
                failed,
            )
        return GhostDetectionResult(
            checked=checked,
            ghosted=ghosted,
            skipped=skipped,
            failed=failed,
        )

    def _process_job(self, user_id: int, job: SeenJob, *, now: datetime) -> str:
        if not self._eligible_for_ghost(job):
            return "skipped"

        ctx = self.inbox.resolve_context(user_id)
        if ctx is None:
            return "skipped"

        mailbox_email = mailbox_email_from_context(ctx)
        if not mailbox_email:
            return "skipped"

        message = build_ghost_summary_message(job=job, mailbox_email=mailbox_email)
        send_result = self.inbox.send_message(user_id, message)
        if send_result.status != "sent":
            logger.warning(
                "ghost summary send failed job=%s user=%s error=%s",
                job.id,
                user_id,
                send_result.error,
            )
            return "failed"

        job.ghosted_at = now
        self.session.flush()
        return "ghosted"

    @staticmethod
    def _eligible_for_ghost(job: SeenJob) -> bool:
        """Only ghost applications that successfully submitted and are awaiting reply."""
        latest = latest_live_attempt(job.application_logs)
        return latest is None or latest.status not in ("queued", "processing", "failed")
