"""Branch coverage for the Gmail adapter (guards, list paging, label creation)."""

import base64
from datetime import UTC, datetime
from email.message import EmailMessage

import pytest
import respx
from httpx import Response

from app.inbox.adapters.gmail import GmailMailbox
from app.inbox.gmail_ids import gmail_message_uid
from app.inbox.types import (
    GmailMailboxConfig,
    MailboxContext,
    OutboundMessage,
    OutlookMailboxConfig,
)

CONFIG = GmailMailboxConfig(
    email_address="user@gmail.com", access_token="access-token", refresh_token="refresh-token"
)
CTX = MailboxContext(connector_type="gmail", config=CONFIG, user_id=1)
BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _raw_b64() -> str:
    message = EmailMessage()
    message["From"] = "hr@company.test"
    message["To"] = "user@gmail.com"
    message["Subject"] = "Follow up"
    message.set_content("Hello there")
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


# --------------------------------------------------------------------------- #
# _config guards
# --------------------------------------------------------------------------- #


def test_config_rejects_wrong_connector_type() -> None:
    ctx = MailboxContext(connector_type="outlook", config=CONFIG, user_id=1)
    with pytest.raises(TypeError, match="connector_type='gmail'"):
        GmailMailbox().fetch_messages(ctx)


def test_config_rejects_wrong_config_type() -> None:
    ctx = MailboxContext(
        connector_type="gmail",
        config=OutlookMailboxConfig(email_address="u@x.test", access_token="a", refresh_token="r"),
        user_id=1,
    )
    with pytest.raises(TypeError, match="GmailMailboxConfig"):
        GmailMailbox().fetch_messages(ctx)


# --------------------------------------------------------------------------- #
# fetch: skip branches + raw None
# --------------------------------------------------------------------------- #


@respx.mock
def test_fetch_skips_bad_entries_and_missing_dates() -> None:
    gid_ok = "id-ok"
    gid_no_date = "id-no-date"
    received = datetime(2026, 6, 30, tzinfo=UTC)
    millis = str(int(received.timestamp() * 1000))
    respx.get(f"{BASE}/messages").mock(
        return_value=Response(
            200,
            json={
                "messages": [
                    "not-a-dict",
                    {"id": ""},
                    {"id": gid_no_date},
                    {"id": gid_ok},
                    {"id": gid_ok},  # duplicate -> seen skip
                ]
            },
        )
    )
    # gid_no_date returns 500 on the metadata probe -> received_at None -> skip.
    respx.get(f"{BASE}/messages/{gid_no_date}").mock(return_value=Response(500))
    respx.get(f"{BASE}/messages/{gid_ok}").mock(
        return_value=Response(200, json={"internalDate": millis, "raw": _raw_b64()})
    )
    result = GmailMailbox().fetch_messages(CTX, limit=10)
    assert [m.raw_headers.get("x-gmail-id") for m in result.messages] == [gid_ok]


@respx.mock
def test_fetch_skips_uid_at_or_below_cursor() -> None:
    gid = "id-old"
    received = datetime(2026, 1, 1, tzinfo=UTC)
    millis = str(int(received.timestamp() * 1000))
    since_uid = gmail_message_uid(gid, received)
    respx.get(f"{BASE}/messages").mock(return_value=Response(200, json={"messages": [{"id": gid}]}))
    respx.get(f"{BASE}/messages/{gid}").mock(
        return_value=Response(200, json={"internalDate": millis, "raw": _raw_b64()})
    )
    result = GmailMailbox().fetch_messages(CTX, since_uid=since_uid, limit=10)
    assert result.messages == []


@respx.mock
def test_fetch_paginates_then_stops() -> None:
    received = datetime(2026, 6, 30, tzinfo=UTC)
    millis = str(int(received.timestamp() * 1000))
    calls = {"n": 0}

    def list_handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return Response(200, json={"messages": [{"id": "g1"}], "nextPageToken": "PAGE2"})
        return Response(200, json={"messages": [{"id": "g2"}]})  # no nextPageToken -> stop

    respx.get(f"{BASE}/messages").mock(side_effect=list_handler)
    for gid in ("g1", "g2"):
        respx.get(f"{BASE}/messages/{gid}").mock(
            return_value=Response(200, json={"internalDate": millis, "raw": _raw_b64()})
        )
    result = GmailMailbox().fetch_messages(CTX, limit=10)
    assert calls["n"] == 2
    assert len(result.messages) == 2


@respx.mock
def test_fetch_exhausts_max_pages() -> None:
    # The list endpoint always returns a nextPageToken, so the paging loop exits by
    # exhausting range(max_pages) rather than via break (branch 189->223).
    received = datetime(2026, 6, 30, tzinfo=UTC)
    millis = str(int(received.timestamp() * 1000))
    counter = {"n": 0}

    def list_handler(request):
        counter["n"] += 1
        gid = f"page-{counter['n']}"
        return Response(
            200, json={"messages": [{"id": gid}], "nextPageToken": f"tok-{counter['n']}"}
        )

    respx.get(f"{BASE}/messages").mock(side_effect=list_handler)
    respx.get(url__regex=rf"{BASE}/messages/page-\d+").mock(
        return_value=Response(200, json={"internalDate": millis, "raw": _raw_b64()})
    )
    result = GmailMailbox().fetch_messages(CTX, limit=5)
    # 20 pages requested (max_pages), each yields one message; limit caps the result.
    assert counter["n"] == 20
    assert len(result.messages) == 5


@respx.mock
def test_fetch_skips_when_raw_unavailable() -> None:
    gid = "g-raw-missing"
    received = datetime(2026, 6, 30, tzinfo=UTC)
    millis = str(int(received.timestamp() * 1000))
    respx.get(f"{BASE}/messages").mock(return_value=Response(200, json={"messages": [{"id": gid}]}))

    # metadata probe (Date) succeeds, but the raw fetch returns 400 -> None -> skip.
    def message_handler(request):
        if request.url.params.get("format") == "raw":
            return Response(400)
        return Response(200, json={"internalDate": millis})

    respx.get(f"{BASE}/messages/{gid}").mock(side_effect=message_handler)
    result = GmailMailbox().fetch_messages(CTX, limit=10)
    assert result.messages == []


@respx.mock
def test_fetch_raw_missing_field_returns_none() -> None:
    gid = "g-noraw-field"
    received = datetime(2026, 6, 30, tzinfo=UTC)
    millis = str(int(received.timestamp() * 1000))
    respx.get(f"{BASE}/messages").mock(return_value=Response(200, json={"messages": [{"id": gid}]}))

    def message_handler(request):
        if request.url.params.get("format") == "raw":
            return Response(200, json={"raw": 123})  # non-str raw -> None
        return Response(200, json={"internalDate": millis})

    respx.get(f"{BASE}/messages/{gid}").mock(side_effect=message_handler)
    assert GmailMailbox().fetch_messages(CTX, limit=10).messages == []


# --------------------------------------------------------------------------- #
# send
# --------------------------------------------------------------------------- #


@respx.mock
def test_send_failure_returns_failed() -> None:
    respx.post(f"{BASE}/messages/send").mock(return_value=Response(500))
    result = GmailMailbox().send_message(
        CTX,
        OutboundMessage(
            to=["hr@x"],
            subject="S",
            body="B",
            in_reply_to="<r@x>",
            references="<a@x>",
            extra_headers={"X-HeadStart-Type": "auto-reply"},
        ),
    )
    assert result.status == "failed"
    assert result.error


# --------------------------------------------------------------------------- #
# test_connection
# --------------------------------------------------------------------------- #


@respx.mock
def test_test_connection_success() -> None:
    respx.get(f"{BASE}/profile").mock(
        return_value=Response(200, json={"emailAddress": "user@gmail.com"})
    )
    result = GmailMailbox().test_connection(CTX)
    assert result.imap_ok is True
    assert result.smtp_ok is True


@respx.mock
def test_test_connection_email_mismatch() -> None:
    respx.get(f"{BASE}/profile").mock(
        return_value=Response(200, json={"emailAddress": "other@gmail.com"})
    )
    result = GmailMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert "does not match" in (result.error or "")


@respx.mock
def test_test_connection_http_error() -> None:
    respx.get(f"{BASE}/profile").mock(return_value=Response(500))
    result = GmailMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.error


# --------------------------------------------------------------------------- #
# move / labels
# --------------------------------------------------------------------------- #


def test_move_without_provider_id_fails() -> None:
    result = GmailMailbox().move_message(CTX, uid=1, destination="HeadStart/General")
    assert result.status == "failed"
    assert "gmail_message_id" in (result.error or "")


@respx.mock
def test_move_creates_label_when_missing() -> None:
    gid = "g-move"
    respx.get(f"{BASE}/labels").mock(
        return_value=Response(200, json={"labels": [{"name": "Other", "id": "L0"}]})
    )
    respx.post(f"{BASE}/labels").mock(return_value=Response(200, json={"id": "L-new"}))
    respx.post(f"{BASE}/messages/{gid}/modify").mock(return_value=Response(200, json={"id": gid}))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_label_creation_failure_returns_failed() -> None:
    respx.get(f"{BASE}/labels").mock(return_value=Response(200, json={"labels": []}))
    respx.post(f"{BASE}/labels").mock(return_value=Response(400))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id="g1"
    )
    assert result.status == "failed"
    assert "Could not create Gmail label" in (result.error or "")


@respx.mock
def test_move_label_create_non_str_id_returns_failed() -> None:
    respx.get(f"{BASE}/labels").mock(return_value=Response(200, json={"labels": []}))
    respx.post(f"{BASE}/labels").mock(return_value=Response(200, json={"id": 123}))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id="g1"
    )
    assert result.status == "failed"


@respx.mock
def test_move_modify_http_error_returns_failed() -> None:
    gid = "g-err"
    respx.get(f"{BASE}/labels").mock(
        return_value=Response(200, json={"labels": [{"name": "HeadStart/General", "id": "L1"}]})
    )
    respx.post(f"{BASE}/messages/{gid}/modify").mock(return_value=Response(500))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "failed"
    assert result.error


@respx.mock
def test_move_list_labels_error_paths() -> None:
    # labels list returns 400 -> [] labels -> label created; label with non-str id
    # is skipped by the name match guard.
    gid = "g-list"
    respx.get(f"{BASE}/labels").mock(return_value=Response(400))
    respx.post(f"{BASE}/labels").mock(return_value=Response(200, json={"id": "L-x"}))
    respx.post(f"{BASE}/messages/{gid}/modify").mock(return_value=Response(200, json={"id": gid}))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_list_labels_non_list_payload() -> None:
    gid = "g-nonlist"
    respx.get(f"{BASE}/labels").mock(return_value=Response(200, json={"labels": "nope"}))
    respx.post(f"{BASE}/labels").mock(return_value=Response(200, json={"id": "L-y"}))
    respx.post(f"{BASE}/messages/{gid}/modify").mock(return_value=Response(200, json={"id": gid}))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_labels_with_non_dict_entries_skipped() -> None:
    gid = "g-mixed"
    respx.get(f"{BASE}/labels").mock(
        return_value=Response(
            200,
            json={"labels": ["not-a-dict", {"name": "HeadStart/General", "id": "L2"}]},
        )
    )
    respx.post(f"{BASE}/messages/{gid}/modify").mock(return_value=Response(200, json={"id": gid}))
    result = GmailMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "moved"
