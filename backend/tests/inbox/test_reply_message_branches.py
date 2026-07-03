"""Branch coverage for recruiter reply message builder."""

import pytest

from app.inbox.reply_message import build_recruiter_reply_message
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft


def _draft() -> InboxReplyDraft:
    return InboxReplyDraft(
        user_id=1,
        inbox_classification_id=1,
        message_uid=7,
        subject="Re: X",
        body_text="Body",
        provider="heuristic",
    )


def test_empty_from_addr_raises() -> None:
    classification = InboxClassification(
        user_id=1,
        message_uid=7,
        message_id="<m@x>",
        label="follow_up",
        confidence=0.9,
        reason="r",
        provider="heuristic",
        subject="S",
        from_addr="   ",
    )
    with pytest.raises(ValueError, match="no from_addr"):
        build_recruiter_reply_message(draft=_draft(), classification=classification)


def test_without_references_payload_uses_message_id_only() -> None:
    classification = InboxClassification(
        user_id=1,
        message_uid=7,
        message_id="<m@x>",
        label="follow_up",
        confidence=0.9,
        reason="r",
        provider="heuristic",
        subject="S",
        from_addr="hr@company.test",
        payload={},
    )
    message = build_recruiter_reply_message(draft=_draft(), classification=classification)
    assert message.references == "<m@x>"
    assert message.in_reply_to == "<m@x>"


def test_references_without_message_id_uses_refs_only() -> None:
    classification = InboxClassification(
        user_id=1,
        message_uid=7,
        message_id=None,
        label="follow_up",
        confidence=0.9,
        reason="r",
        provider="heuristic",
        subject="S",
        from_addr="hr@company.test",
        payload={"references": "<root@x>"},
    )
    message = build_recruiter_reply_message(draft=_draft(), classification=classification)
    assert message.references == "<root@x>"
