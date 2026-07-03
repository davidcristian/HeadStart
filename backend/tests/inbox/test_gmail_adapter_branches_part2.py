"""Branch coverage for the Gmail adapter (send, test_connection, move/labels)."""

import base64
from email.message import EmailMessage

import respx
from httpx import Response

from app.inbox.adapters.gmail import GmailMailbox
from app.inbox.types import (
    GmailMailboxConfig,
    MailboxContext,
    OutboundMessage,
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
