"""Branch coverage for JMAP Email -> InboxMessage conversion."""

from datetime import UTC, datetime

from app.inbox.fastmail_jmap_parse import (
    JMAP_EMAIL_ID_HEADER,
    jmap_email_to_inbox_message,
)


def test_full_structured_email() -> None:
    email = {
        "id": "M1",
        "receivedAt": "2026-06-30T12:00:00Z",
        "messageId": "<mid@x>",
        "inReplyTo": "<reply@x>",
        "references": ["<a@x>", "<b@x>"],
        "from": [{"email": "hr@company.test"}],
        "to": [{"email": "user@fastmail.test"}],
        "subject": "Interview",
        "headers": [
            {"name": "X-Custom", "value": "yes"},
        ],
        "textBody": [{"partId": "body", "type": "text/plain"}],
        "bodyValues": {"body": {"value": "Hello there"}},
    }
    msg = jmap_email_to_inbox_message(email, uid=99)
    assert msg.uid == 99
    assert msg.from_addr == "hr@company.test"
    assert msg.to_addrs == ["user@fastmail.test"]
    assert msg.subject == "Interview"
    assert msg.message_id == "<mid@x>"
    assert msg.in_reply_to == "<reply@x>"
    assert msg.references == "<a@x> <b@x>"
    assert msg.body_text == "Hello there"
    assert msg.raw_headers[JMAP_EMAIL_ID_HEADER] == "M1"


def test_falls_back_to_headers_when_structured_fields_missing() -> None:
    # No structured from/to/subject -> read from headers map; header Message-ID,
    # In-Reply-To and References take precedence over the structured JMAP fields.
    email = {
        "id": 12345,  # non-str id -> stored as empty header
        "headers": [
            {"name": "From", "value": "hr@company.test"},
            {"name": "To", "value": "Cand <user@fastmail.test>"},
            {"name": "Subject", "value": "Header subject"},
            {"name": "Message-ID", "value": "<hmid@x>"},
            {"name": "In-Reply-To", "value": "<hreply@x>"},
            {"name": "References", "value": "<hr1@x> <hr2@x>"},
            {"name": 123, "value": "ignored-bad-name"},
            "not-a-dict",
        ],
    }
    msg = jmap_email_to_inbox_message(email, uid=1)
    assert msg.from_addr == "hr@company.test"
    assert msg.to_addrs == ["user@fastmail.test"]
    assert msg.subject == "Header subject"
    assert msg.message_id == "<hmid@x>"
    assert msg.in_reply_to == "<hreply@x>"
    assert msg.references == "<hr1@x> <hr2@x>"
    assert msg.raw_headers[JMAP_EMAIL_ID_HEADER] == ""


def test_empty_and_malformed_containers() -> None:
    # from/subject fall back to the From/Subject headers; the malformed structured
    # fields exercise the not-a-list / non-str guards.
    email = {
        "id": "M2",
        "headers": [
            {"name": "From", "value": "sender@x"},
            {"name": "Subject", "value": "Fallback subj"},
        ],
        "from": "not-a-list",  # -> "" then header fallback
        "to": [123, {"no_email": True}, {"email": ""}, {"email": "ok@x"}],
        "references": 42,  # not list/str -> None
        "subject": 999,  # non-str subject -> header fallback
        "receivedAt": "",  # -> None
        "bodyValues": "not-a-dict",  # -> "" body
    }
    msg = jmap_email_to_inbox_message(email, uid=2)
    assert msg.from_addr == "sender@x"
    assert msg.to_addrs == ["ok@x"]
    assert msg.references is None
    assert msg.subject == "Fallback subj"
    assert msg.received_at is None
    assert msg.body_text == ""


def test_references_string_form_and_empty_list() -> None:
    base = {
        "headers": [
            {"name": "From", "value": "a@x"},
            {"name": "Subject", "value": "S"},
        ]
    }
    assert (
        jmap_email_to_inbox_message({**base, "id": "M3", "references": "<x@x>"}, uid=3).references
        == "<x@x>"
    )
    assert (
        jmap_email_to_inbox_message({**base, "id": "M4", "references": []}, uid=4).references
        is None
    )


def test_received_at_naive_and_invalid() -> None:
    base = {
        "headers": [
            {"name": "From", "value": "a@x"},
            {"name": "Subject", "value": "S"},
        ]
    }
    naive = jmap_email_to_inbox_message(
        {**base, "id": "M5", "receivedAt": "2026-06-30T12:00:00"}, uid=5
    ).received_at
    assert naive == datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    invalid = jmap_email_to_inbox_message(
        {**base, "id": "M6", "receivedAt": "not-a-date"}, uid=6
    ).received_at
    assert invalid is None


def test_body_falls_back_to_first_body_value() -> None:
    # textBody references a missing partId, then loop skips non-dict parts;
    # the fallback scans bodyValues for the first dict with a str value.
    email = {
        "id": "M7",
        "headers": [{"name": "From", "value": "a@x"}, {"name": "Subject", "value": "S"}],
        "textBody": ["not-a-dict", {"noPartId": True}, {"partId": 5}, {"partId": "missing"}],
        "bodyValues": {
            "missing": "not-a-dict-entry",
            "other": {"value": ""},  # empty string skipped in fallback
            "real": {"value": "fallback body"},
        },
    }
    assert jmap_email_to_inbox_message(email, uid=7).body_text == "fallback body"


def test_body_partid_hit_with_non_str_value_skipped() -> None:
    # partId matches but its entry value is non-str -> the fallback scan runs.
    email = {
        "id": "M8",
        "headers": [{"name": "From", "value": "a@x"}, {"name": "Subject", "value": "S"}],
        "textBody": [{"partId": "body"}],
        "bodyValues": {"body": {"value": 123}, "z": {"value": "second"}},
    }
    assert jmap_email_to_inbox_message(email, uid=8).body_text == "second"


def test_headers_not_a_list_yields_empty_headers_map() -> None:
    # headers is not a list -> _headers_map returns {} (line 41); from/subject then
    # come from the structured JMAP fields.
    email = {
        "id": "M10",
        "headers": "not-a-list",
        "from": [{"email": "struct@x"}],
        "subject": "Structured subj",
    }
    msg = jmap_email_to_inbox_message(email, uid=10)
    assert msg.from_addr == "struct@x"
    assert msg.subject == "Structured subj"


def test_body_fallback_loop_exhausts_to_empty() -> None:
    # bodyValues has only non-dict or empty/non-str entries and textBody yields no
    # match, so the fallback loop runs to completion and returns "" (branch 124->129).
    email = {
        "id": "M9",
        "headers": [{"name": "From", "value": "a@x"}, {"name": "Subject", "value": "S"}],
        "textBody": [],
        "bodyValues": {"a": "not-a-dict", "b": {"value": 5}, "c": {"value": ""}},
    }
    assert jmap_email_to_inbox_message(email, uid=9).body_text == ""
