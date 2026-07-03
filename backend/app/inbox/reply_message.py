"""Build outbound recruiter reply messages for auto-send."""

from __future__ import annotations

from app.inbox.types import OutboundMessage
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft


def build_recruiter_reply_message(
    *,
    draft: InboxReplyDraft,
    classification: InboxClassification,
) -> OutboundMessage:
    """Compose a threaded reply to the recruiter who sent the inbound message."""
    to_addr = classification.from_addr.strip()
    if not to_addr:
        raise ValueError("classification has no from_addr for reply routing")

    in_reply_to = classification.message_id
    references = classification.message_id
    payload = classification.payload or {}
    if isinstance(payload.get("references"), str) and payload["references"].strip():
        refs = payload["references"].strip()
        if classification.message_id:
            references = f"{refs} {classification.message_id}".strip()
        else:
            references = refs

    return OutboundMessage(
        to=[to_addr],
        subject=draft.subject,
        body=draft.body_text,
        in_reply_to=in_reply_to,
        references=references,
        extra_headers={"X-HeadStart-Type": "auto-reply"},
    )
