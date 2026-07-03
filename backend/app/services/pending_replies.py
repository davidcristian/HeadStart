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

logger = get_logger(__name__)

MIN_REPLY_DELAY_SECONDS = 60


@dataclass(frozen=True)
class PendingReplyProcessResult:
    """Outcome of one pending-reply send pass."""

    checked: int
    sent: int
    failed: int
    skipped: int


class PendingReplyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.inbox = InboxService(session)
        self.credentials = MailboxCredentialRepository(session)
        self.pending = InboxPendingReplyRepository(session)

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

        existing = self.pending.get_by_draft(user_id, draft.id)
        if existing is not None and existing.status in {"pending", "ready"}:
            return existing

        if existing is not None:
            self.pending.cancel_for_draft(user_id, draft.id)

        send_after = self.compute_send_after(anchor=anchor)
        row = InboxPendingReply(
            user_id=user_id,
            inbox_reply_draft_id=draft.id,
            send_after=send_after,
            status="pending",
            payload={"queued_at": utcnow().isoformat()},
        )
        draft.status = "queued"
        self.pending.add(row)
        return row

    def process_due(self, *, now: datetime | None = None) -> PendingReplyProcessResult:
        """Send due pending replies for users with auto-reply enabled."""
        if not settings.inbox_agent_enabled:
            return PendingReplyProcessResult(checked=0, sent=0, failed=0, skipped=0)

        current = now or utcnow()
        checked = 0
        sent = 0
        failed = 0
        skipped = 0

        for row in self.pending.list_due(now=current):
            checked += 1
            outcome = self._send_one(row, now=current)
            if outcome == "sent":
                sent += 1
            elif outcome == "failed":
                failed += 1
            else:
                skipped += 1

        if sent or failed:
            logger.info(
                "pending replies: checked=%d sent=%d failed=%d skipped=%d",
                checked,
                sent,
                failed,
                skipped,
            )
        return PendingReplyProcessResult(
            checked=checked,
            sent=sent,
            failed=failed,
            skipped=skipped,
        )

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

        try:
            message = build_recruiter_reply_message(draft=draft, classification=classification)
            result = self.inbox.send_message(row.user_id, message)
        except Exception as exc:
            row.status = "failed"
            row.error = str(exc)
            draft.status = "failed"
            self.session.flush()
            return "failed"

        if result.status != "sent":
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
        self.session.flush()
        return "sent"

    def queue_snapshot(self, user_id: int, draft_id: int) -> tuple[str | None, datetime | None]:
        """Return queue status and send_after for one draft, if queued."""
        row = self.pending.get_by_draft(user_id, draft_id)
        if row is None:
            return None, None
        return row.status, row.send_after
