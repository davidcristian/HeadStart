"""Human-like delayed auto-send for recruiter reply drafts."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.inbox.reply_message import build_recruiter_reply_message
from app.inbox.routing import merge_routing_config
from app.models.base import utcnow
from app.models.inbox_pending_reply import InboxPendingReply
from app.models.inbox_reply_draft import InboxReplyDraft
from app.repositories.inbox_pending_replies import InboxPendingReplyRepository
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.services.inbox import InboxService
from app.services.reply_safe_send import ReplySafeSendService

logger = get_logger(__name__)

MIN_REPLY_DELAY_SECONDS = 60

# In-flight lease statuses that must not be re-queued by enqueue_for_draft.
_IN_FLIGHT_STATUSES = frozenset({"pending", "ready", "sending"})


@dataclass(frozen=True)
class PendingReplyProcessResult:
    """Outcome of one pending-reply send pass."""

    checked: int
    sent: int
    failed: int
    skipped: int
    blocked: int


class PendingReplyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.inbox = InboxService(session)
        self.credentials = MailboxCredentialRepository(session)
        self.pending = InboxPendingReplyRepository(session)
        self.safe_send = ReplySafeSendService(session)

    def auto_reply_enabled(self, user_id: int) -> bool:
        """Return whether the user opted into autonomous recruiter replies."""
        credential = self.credentials.get_for_user(user_id)
        if credential is None:
            return False
        config = merge_routing_config(credential.routing_config)
        return config.auto_reply_enabled

    def compute_send_after(
        self,
        *,
        now: datetime | None = None,
        anchor: datetime | None = None,
    ) -> datetime:
        """Return the earliest auto-send instant with configured delay and jitter."""
        current = now or utcnow()
        base = anchor or current
        min_delay = max(MIN_REPLY_DELAY_SECONDS, int(settings.inbox_reply_min_delay_seconds))
        jitter_cap = max(0, int(settings.inbox_reply_delay_jitter_seconds))
        jitter = random.randint(0, jitter_cap) if jitter_cap else 0
        return base + timedelta(seconds=min_delay + jitter)

    def enqueue_for_draft(
        self,
        user_id: int,
        draft: InboxReplyDraft,
        *,
        anchor: datetime | None = None,
    ) -> InboxPendingReply | None:
        """Queue one draft for delayed auto-send when the user opted in."""
        if not self.auto_reply_enabled(user_id):
            return None

        classification = draft.classification
        queue_decision = self.safe_send.evaluate_before_queue(draft, classification)
        if not queue_decision.allowed:
            self.safe_send.record(user_id, draft, queue_decision, classification=classification)
            return None

        existing = self.pending.get_by_draft(user_id, draft.id)
        if existing is not None and existing.status in _IN_FLIGHT_STATUSES:
            return existing

        send_after = self.compute_send_after(anchor=anchor)
        draft.status = "queued"
        if existing is not None:
            # A terminal (sent/failed/cancelled/blocked) row for this draft already exists; the
            # unique constraint on inbox_reply_draft_id means we must re-queue it in place rather
            # than insert a duplicate.
            existing.status = "pending"
            existing.send_after = send_after
            existing.sent_at = None
            existing.error = None
            existing.payload = {"queued_at": utcnow().isoformat()}
            row = existing
        else:
            row = InboxPendingReply(
                user_id=user_id,
                inbox_reply_draft_id=draft.id,
                send_after=send_after,
                status="pending",
                payload={"queued_at": utcnow().isoformat()},
            )
            self.pending.add(row)
        self.session.flush()
        self.safe_send.record(
            user_id,
            draft,
            queue_decision,
            pending=row,
            classification=classification,
        )
        return row

    def claim_due_ids(self, *, now: datetime | None = None, limit: int = 100) -> list[int]:
        """Lease due pending replies (flip to ``sending``) and return their ids.

        Caller must commit before SMTP so overlapping ticks / ``acks_late``
        redelivery cannot re-select the same rows.
        """
        if not settings.inbox_agent_enabled:
            return []
        current = now or utcnow()
        return [row.id for row in self.pending.claim_due(now=current, limit=limit)]

    def process_claimed(
        self,
        reply_ids: list[int],
        *,
        now: datetime | None = None,
    ) -> PendingReplyProcessResult:
        """SMTP-send previously leased rows and mark each terminal outcome."""
        if not settings.inbox_agent_enabled or not reply_ids:
            return PendingReplyProcessResult(checked=0, sent=0, failed=0, skipped=0, blocked=0)

        current = now or utcnow()
        checked = 0
        sent = 0
        failed = 0
        skipped = 0
        blocked = 0

        for reply_id in reply_ids:
            row = self.pending.get_claimed(reply_id)
            if row is None:
                continue
            checked += 1
            outcome = self._send_one(row, now=current)
            if outcome == "sent":
                sent += 1
            elif outcome == "failed":
                failed += 1
            elif outcome == "blocked":
                blocked += 1
            else:
                skipped += 1

        if sent or failed or blocked:
            logger.info(
                "pending replies: checked=%d sent=%d failed=%d skipped=%d blocked=%d",
                checked,
                sent,
                failed,
                skipped,
                blocked,
            )
        return PendingReplyProcessResult(
            checked=checked,
            sent=sent,
            failed=failed,
            skipped=skipped,
            blocked=blocked,
        )

    def process_due(self, *, now: datetime | None = None) -> PendingReplyProcessResult:
        """Claim and send due pending replies in one session (tests / single-worker).

        Production beat uses ``claim_due_ids`` then ``process_claimed`` across two
        transactions so the ``sending`` lease is committed before SMTP.
        """
        if not settings.inbox_agent_enabled:
            return PendingReplyProcessResult(checked=0, sent=0, failed=0, skipped=0, blocked=0)

        current = now or utcnow()
        reply_ids = [row.id for row in self.pending.claim_due(now=current)]
        return self.process_claimed(reply_ids, now=current)

    def _send_one(self, row: InboxPendingReply, *, now: datetime) -> str:
        if not self.auto_reply_enabled(row.user_id):
            row.status = "cancelled"
            if row.draft is not None:
                row.draft.status = "draft"
            self.session.flush()
            return "skipped"

        draft = row.draft
        if draft is None:
            row.status = "failed"
            row.error = "draft missing"
            self.session.flush()
            return "failed"

        classification = draft.classification
        if classification is None:
            row.status = "failed"
            row.error = "classification missing"
            draft.status = "failed"
            self.session.flush()
            return "failed"

        send_decision, reservation = self.safe_send.reserve_before_send(
            row.user_id,
            draft,
            classification,
            pending=row,
            now=now,
        )
        if not send_decision.allowed:
            row.status = "blocked"
            row.error = send_decision.reason
            draft.status = "draft"
            self.session.flush()
            return "blocked"

        # Publish the reserved rate slot before SMTP so overlapping workers see it.
        self.session.commit()

        try:
            message = build_recruiter_reply_message(draft=draft, classification=classification)
            result = self.inbox.send_message(row.user_id, message)
        except Exception as exc:
            self.safe_send.release_reservation(reservation)
            row.status = "failed"
            row.error = str(exc)
            draft.status = "failed"
            self.session.flush()
            return "failed"

        if result.status != "sent":
            self.safe_send.release_reservation(reservation)
            row.status = "failed"
            row.error = result.error or "send failed"
            draft.status = "failed"
            self.session.flush()
            return "failed"

        row.status = "sent"
        row.sent_at = now
        row.error = None
        draft.status = "sent"
        payload = dict(row.payload or {})
        payload["sent_via"] = "auto_reply"
        row.payload = payload
        self.safe_send.finalize_reservation(reservation)
        self.session.flush()
        return "sent"

    def queue_snapshot(self, user_id: int, draft_id: int) -> tuple[str | None, datetime | None]:
        """Return queue status and send_after for one draft, if queued."""
        row = self.pending.get_by_draft(user_id, draft_id)
        if row is None:
            return None, None
        return row.status, row.send_after
