"""Unit tests for recruiter reply outbound message builder."""

from app.inbox.reply_message import build_recruiter_reply_message
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft


def test_build_recruiter_reply_message_threads_headers() -> None:
    classification = InboxClassification(
        user_id=1,
        message_uid=7,
        message_id="<msg-7@acme.com>",
        label="follow_up",
        confidence=0.9,
        reason="test",
        provider="heuristic",
        subject="Availability?",
        from_addr="Recruiter <hr@acme.com>",
        payload={"references": "<root@acme.com>"},
    )
    draft = InboxReplyDraft(
        user_id=1,
        inbox_classification_id=1,
        message_uid=7,
        subject="Re: Availability?",
        body_text="I am available next week.",
        provider="heuristic",
    )
    message = build_recruiter_reply_message(draft=draft, classification=classification)
    assert message.to == ["Recruiter <hr@acme.com>"]
    assert message.in_reply_to == "<msg-7@acme.com>"
    assert message.references == "<root@acme.com> <msg-7@acme.com>"
    assert message.extra_headers["X-HeadStart-Type"] == "auto-reply"
