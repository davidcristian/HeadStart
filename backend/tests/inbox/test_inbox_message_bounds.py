"""InboxMessage field bounds and mailbox-parser clipping."""

from __future__ import annotations

from email.message import EmailMessage

import pytest
from pydantic import ValidationError

from app.inbox.fastmail_jmap_parse import jmap_email_to_inbox_message
from app.inbox.parse import parse_rfc822
from app.inbox.types import (
    INBOX_ADDR_MAX_LENGTH,
    INBOX_BODY_MAX_LENGTH,
    INBOX_HEADER_NAME_MAX_LENGTH,
    INBOX_HEADER_VALUE_MAX_LENGTH,
    INBOX_MESSAGE_ID_MAX_LENGTH,
    INBOX_RAW_HEADERS_MAX_ITEMS,
    INBOX_SUBJECT_MAX_LENGTH,
    INBOX_TO_ADDRS_MAX_ITEMS,
    InboxMessage,
    clip_inbox_headers,
    clip_inbox_str,
)
from app.schemas.inbox_classification import EmailClassifyRequest


def test_inbox_message_rejects_overlong_subject() -> None:
    with pytest.raises(ValidationError, match="subject"):
        InboxMessage(uid=1, subject="x" * (INBOX_SUBJECT_MAX_LENGTH + 1))


def test_inbox_message_rejects_overlong_body() -> None:
    with pytest.raises(ValidationError, match="body_text"):
        InboxMessage(uid=1, body_text="y" * (INBOX_BODY_MAX_LENGTH + 1))


def test_inbox_message_rejects_overlong_from_addr() -> None:
    with pytest.raises(ValidationError, match="from_addr"):
        InboxMessage(uid=1, from_addr="a" * (INBOX_ADDR_MAX_LENGTH + 1))


def test_inbox_message_rejects_too_many_to_addrs() -> None:
    with pytest.raises(ValidationError, match="to_addrs"):
        InboxMessage(
            uid=1,
            to_addrs=[f"u{i}@example.com" for i in range(INBOX_TO_ADDRS_MAX_ITEMS + 1)],
        )


def test_inbox_message_rejects_overlong_to_addr_entry() -> None:
    with pytest.raises(ValidationError, match="to_addrs entry"):
        InboxMessage(uid=1, to_addrs=["x" * (INBOX_ADDR_MAX_LENGTH + 1)])


def test_inbox_message_rejects_too_many_raw_headers() -> None:
    with pytest.raises(ValidationError, match="raw_headers"):
        InboxMessage(
            uid=1,
            raw_headers={f"X-H{i}": "v" for i in range(INBOX_RAW_HEADERS_MAX_ITEMS + 1)},
        )


def test_inbox_message_rejects_overlong_header_name() -> None:
    with pytest.raises(ValidationError, match="raw_headers key"):
        InboxMessage(uid=1, raw_headers={"K" * (INBOX_HEADER_NAME_MAX_LENGTH + 1): "v"})


def test_inbox_message_rejects_overlong_header_value() -> None:
    with pytest.raises(ValidationError, match="raw_headers value"):
        InboxMessage(
            uid=1,
            raw_headers={"X-Big": "v" * (INBOX_HEADER_VALUE_MAX_LENGTH + 1)},
        )


def test_classify_request_rejects_overlong_body_via_message() -> None:
    with pytest.raises(ValidationError, match="body_text"):
        EmailClassifyRequest(
            message=InboxMessage(uid=1, body_text="z" * (INBOX_BODY_MAX_LENGTH + 1))
        )


def test_clip_inbox_str_none_and_short() -> None:
    assert clip_inbox_str(None, 10) is None
    assert clip_inbox_str("hi", 10) == "hi"
    assert clip_inbox_str("abcdefghij", 5) == "abcde"


def test_clip_inbox_headers_caps_items_and_lengths() -> None:
    headers = {f"X-H{i}": "v" * 10 for i in range(INBOX_RAW_HEADERS_MAX_ITEMS + 5)}
    headers["K" * (INBOX_HEADER_NAME_MAX_LENGTH + 3)] = "short"
    headers["X-Val"] = "v" * (INBOX_HEADER_VALUE_MAX_LENGTH + 7)
    clipped = clip_inbox_headers(headers)
    assert len(clipped) == INBOX_RAW_HEADERS_MAX_ITEMS
    assert all(len(k) <= INBOX_HEADER_NAME_MAX_LENGTH for k in clipped)
    assert all(len(v) <= INBOX_HEADER_VALUE_MAX_LENGTH for v in clipped.values())


def test_parse_rfc822_clips_oversized_fields() -> None:
    msg = EmailMessage()
    msg["From"] = "a" * (INBOX_ADDR_MAX_LENGTH + 40) + "@example.com"
    msg["To"] = ", ".join(f"u{i}@example.com" for i in range(INBOX_TO_ADDRS_MAX_ITEMS + 10))
    msg["Subject"] = "S" * (INBOX_SUBJECT_MAX_LENGTH + 50)
    msg["Message-ID"] = "<" + ("m" * (INBOX_SUBJECT_MAX_LENGTH + 20)) + "@x>"
    msg["In-Reply-To"] = "<" + ("r" * (INBOX_SUBJECT_MAX_LENGTH + 20)) + "@x>"
    msg["References"] = " ".join(f"<ref{i}@x>" for i in range(500))
    for i in range(INBOX_RAW_HEADERS_MAX_ITEMS + 5):
        msg[f"X-Extra-{i}"] = "v"
    msg.set_content("B" * (INBOX_BODY_MAX_LENGTH + 100))
    parsed = parse_rfc822(uid=3, raw_bytes=msg.as_bytes())
    assert len(parsed.subject) == INBOX_SUBJECT_MAX_LENGTH
    assert len(parsed.body_text) == INBOX_BODY_MAX_LENGTH
    assert len(parsed.from_addr) == INBOX_ADDR_MAX_LENGTH
    assert len(parsed.to_addrs) == INBOX_TO_ADDRS_MAX_ITEMS
    assert parsed.message_id is not None and len(parsed.message_id) <= INBOX_MESSAGE_ID_MAX_LENGTH
    assert len(parsed.raw_headers) <= INBOX_RAW_HEADERS_MAX_ITEMS


def test_jmap_parse_clips_oversized_fields() -> None:
    email = {
        "id": "M-big",
        "messageId": "<" + ("m" * 2000) + "@x>",
        "inReplyTo": "<" + ("r" * 2000) + "@x>",
        "references": " ".join(f"<ref{i}@x>" for i in range(500)),
        "from": [{"email": "a" * (INBOX_ADDR_MAX_LENGTH + 20) + "@x.com"}],
        "to": [{"email": f"u{i}@x.com"} for i in range(INBOX_TO_ADDRS_MAX_ITEMS + 5)],
        "subject": "S" * (INBOX_SUBJECT_MAX_LENGTH + 10),
        "headers": [
            {"name": f"X-H{i}", "value": "v"} for i in range(INBOX_RAW_HEADERS_MAX_ITEMS + 3)
        ],
        "textBody": [{"partId": "body", "type": "text/plain"}],
        "bodyValues": {"body": {"value": "B" * (INBOX_BODY_MAX_LENGTH + 50)}},
    }
    msg = jmap_email_to_inbox_message(email, uid=8)
    assert len(msg.subject) == INBOX_SUBJECT_MAX_LENGTH
    assert len(msg.body_text) == INBOX_BODY_MAX_LENGTH
    assert len(msg.from_addr) == INBOX_ADDR_MAX_LENGTH
    assert len(msg.to_addrs) == INBOX_TO_ADDRS_MAX_ITEMS
    assert msg.message_id is not None and len(msg.message_id) <= INBOX_MESSAGE_ID_MAX_LENGTH
    assert len(msg.raw_headers) <= INBOX_RAW_HEADERS_MAX_ITEMS
