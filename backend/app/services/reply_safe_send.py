"""Evaluate safe-send guardrails before autonomous recruiter replies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.safe_send import TopicBlockResult, check_topic_blocklist
from app.models.base import utcnow
from app.models.inbox_classification import InboxClassification
from app.models.inbox_pending_reply import InboxPendingReply
from app.models.inbox_reply_draft import InboxReplyDraft
from app.models.inbox_reply_send_log import InboxReplySendLog
from app.repositories.inbox_reply_send_logs import InboxReplySendLogRepository
from app.services.inbox import InboxService
from app.services.inbox_gate import auto_reply_recipient_allowed

SENT_OUTCOME = "sent"
BLOCKED_TOPIC_OUTCOME = "blocked_topic"
BLOCKED_RATE_HOUR_OUTCOME = "blocked_rate_limit_hour"
BLOCKED_RATE_DAY_OUTCOME = "blocked_rate_limit_day"
BLOCKED_RECIPIENT_OUTCOME = "blocked_recipient"
BODY_EXCERPT_MAX_CHARS = 500


@dataclass(frozen=True)
class SafeSendDecision:
    """Whether an auto-reply may be sent."""

    allowed: bool
    outcome: str
    reason: str
    payload: dict[str, Any]


class ReplySafeSendService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.logs = InboxReplySendLogRepository(session)
        self.inbox = InboxService(session)

    def evaluate_before_queue(
        self,
        draft: InboxReplyDraft,
        classification: InboxClassification | None,
    ) -> SafeSendDecision:
        """Block queueing when the draft or inbound mail hits the topic filter."""
        topic = self._topic_block(draft, classification)
        if topic is not None:
            return SafeSendDecision(
                allowed=False,
                outcome=BLOCKED_TOPIC_OUTCOME,
                reason=topic.reason,
                payload={"matched_topics": list(topic.matched_topics)},
            )
        return SafeSendDecision(allowed=True, outcome="queued", reason="", payload={})

    def evaluate_before_send(
        self,
        user_id: int,
        draft: InboxReplyDraft,
        classification: InboxClassification | None,
        *,
        now: datetime | None = None,
    ) -> SafeSendDecision:
        """Apply topic and rate-limit guardrails immediately before SMTP send."""
        current = now or utcnow()

        topic = self._topic_block(draft, classification)
        if topic is not None:
            return SafeSendDecision(
                allowed=False,
                outcome=BLOCKED_TOPIC_OUTCOME,
                reason=topic.reason,
                payload={"matched_topics": list(topic.matched_topics)},
            )

        if classification is not None and not auto_reply_recipient_allowed(
            self.session,
            from_addr=classification.from_addr,
            classification=classification,
        ):
            return SafeSendDecision(
                allowed=False,
                outcome=BLOCKED_RECIPIENT_OUTCOME,
                reason=(
                    "Auto-reply blocked: recipient does not match the linked "
                    "application employer domain."
                ),
                payload={},
            )

        hourly_cap = int(settings.inbox_reply_max_per_hour)
        if hourly_cap > 0:
            hour_count = self.logs.count_sent_since(user_id, since=current - timedelta(hours=1))
            if hour_count >= hourly_cap:
                return SafeSendDecision(
                    allowed=False,
                    outcome=BLOCKED_RATE_HOUR_OUTCOME,
                    reason=(
                        f"Auto-reply blocked: hourly limit reached " f"({hour_count}/{hourly_cap})."
                    ),
                    payload={"sent_last_hour": hour_count, "limit": hourly_cap},
                )

        daily_cap = int(settings.inbox_reply_max_per_day)
        if daily_cap > 0:
            day_count = self.logs.count_sent_since(user_id, since=current - timedelta(days=1))
            if day_count >= daily_cap:
                return SafeSendDecision(
                    allowed=False,
                    outcome=BLOCKED_RATE_DAY_OUTCOME,
                    reason=(f"Auto-reply blocked: daily limit reached ({day_count}/{daily_cap})."),
                    payload={"sent_last_day": day_count, "limit": daily_cap},
                )

        return SafeSendDecision(allowed=True, outcome=SENT_OUTCOME, reason="", payload={})

    def record(
        self,
        user_id: int,
        draft: InboxReplyDraft,
        decision: SafeSendDecision,
        *,
        pending: InboxPendingReply | None = None,
        classification: InboxClassification | None = None,
    ) -> InboxReplySendLog:
        """Persist an audit row for a queue or send decision."""
        inbound_body = self._inbound_body(classification)
        row = InboxReplySendLog(
            user_id=user_id,
            inbox_reply_draft_id=draft.id,
            inbox_pending_reply_id=pending.id if pending is not None else None,
            outcome=decision.outcome,
            reason=decision.reason,
            subject=draft.subject,
            body_excerpt=self._body_excerpt(draft.body_text),
            payload={
                **decision.payload,
                "inbound_subject": (classification.subject if classification else ""),
                "inbound_from": (classification.from_addr if classification else ""),
                "inbound_body_excerpt": inbound_body[:BODY_EXCERPT_MAX_CHARS],
            },
        )
        return self.logs.add(row)

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[InboxReplySendLog]:
        """Return recent auto-reply audit rows for one user."""
        self.inbox.require_enabled()
        return self.logs.list_for_user(user_id, limit=limit)

    def _topic_block(
        self,
        draft: InboxReplyDraft,
        classification: InboxClassification | None,
    ) -> TopicBlockResult | None:
        inbound_body = self._inbound_body(classification)
        inbound_subject = classification.subject if classification is not None else ""
        return check_topic_blocklist(
            inbound_subject=inbound_subject,
            inbound_body=inbound_body,
            draft_subject=draft.subject,
            draft_body=draft.body_text,
        )

    def _inbound_body(self, classification: InboxClassification | None) -> str:
        if classification is None or not classification.payload:
            return ""
        excerpt = classification.payload.get("body_excerpt")
        return str(excerpt) if isinstance(excerpt, str) else ""

    def _body_excerpt(self, body: str) -> str:
        text = body.strip()
        if len(text) <= BODY_EXCERPT_MAX_CHARS:
            return text
        return text[: BODY_EXCERPT_MAX_CHARS - 1].rstrip() + "\u2026"
