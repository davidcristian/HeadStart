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

    def claim_due_ids(self, *, now: datetime | None = None, limit: int = 100) -> list[int]:
        """Lease stale applications (stamp ``ghosted_at``) and return their ids.

        Caller must commit before SMTP so overlapping ticks / ``acks_late``
        redelivery cannot re-select the same row (XCT-11). Ineligible jobs and
        users without a mailbox are released immediately and not returned.
        """
        if not settings.inbox_agent_enabled:
            return []

        current = now or utcnow()
        cutoff = current - timedelta(days=settings.inbox_ghost_window_days)
        claimed_ids: list[int] = []

        for user_id, job in self.repo.claim_stale_applications(
            cutoff=cutoff, now=current, limit=limit
        ):
            if not self._eligible_for_ghost(job):
                self.repo.release_claim(job)
                continue
            ctx = self.inbox.resolve_context(user_id)
            if ctx is None:
                self.repo.release_claim(job)
                continue
            mailbox_email = mailbox_email_from_context(ctx)
            if not mailbox_email:
                self.repo.release_claim(job)
                continue
            claimed_ids.append(job.id)

        return claimed_ids

    def process_claimed(self, job_ids: list[int]) -> GhostDetectionResult:
        """SMTP-send ghost summaries for previously leased jobs.

        Per-item isolation (SVC-06): a raise from one job is logged and counted
        as failed so other leased jobs still process. Failed sends and skips
        release the ``ghosted_at`` lease so the next tick can retry.
        """
        checked = 0
        ghosted = 0
        skipped = 0
        failed = 0

        for job_id in job_ids:
            checked += 1
            try:
                outcome = self._send_claimed(job_id)
                if outcome == "ghosted":
                    self.session.commit()
                    ghosted += 1
                elif outcome == "failed":
                    self.session.commit()
                    failed += 1
                else:
                    self.session.commit()
                    skipped += 1
            except Exception:
                self.session.rollback()
                claimed = self.repo.get_claimed(job_id)
                if claimed is not None:
                    _, job = claimed
                    self.repo.release_claim(job)
                    self.session.commit()
                logger.exception(
                    "ghost detection failed for job %s; continuing",
                    job_id,
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

    def process_due(self, *, now: datetime | None = None) -> GhostDetectionResult:
        """Claim then send in one session (tests / helpers).

        Commits the ``ghosted_at`` lease before SMTP so a mid-batch rollback
        cannot clear other jobs' claims. Production beat uses ``claim_due_ids``
        then ``process_claimed`` across two ``session_scope`` transactions.
        """
        current = now or utcnow()
        job_ids = self.claim_due_ids(now=current)
        self.session.commit()
        return self.process_claimed(job_ids)

    def _send_claimed(self, job_id: int) -> str:
        claimed = self.repo.get_claimed(job_id)
        if claimed is None:
            return "skipped"

        user_id, job = claimed
        ctx = self.inbox.resolve_context(user_id)
        if ctx is None:
            self.repo.release_claim(job)
            return "skipped"

        mailbox_email = mailbox_email_from_context(ctx)
        if not mailbox_email:
            self.repo.release_claim(job)
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
            self.repo.release_claim(job)
            return "failed"

        # Lease already stamped ``ghosted_at`` at claim time; keep it.
        return "ghosted"

    @staticmethod
    def _eligible_for_ghost(job: SeenJob) -> bool:
        """Only ghost applications that successfully submitted and are awaiting reply."""
        latest = latest_live_attempt(job.application_logs)
        return latest is None or latest.status not in ("queued", "processing", "failed")
