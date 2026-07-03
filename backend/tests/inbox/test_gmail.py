"""Tests for the Gmail mailbox adapter (mocked Gmail API)."""

import base64
from email.message import EmailMessage

import respx
from httpx import Response

from app.inbox.adapters.gmail import GmailMailbox
from app.inbox.gmail_ids import gmail_id_to_uid
from app.inbox.types import GmailMailboxConfig, MailboxContext, OutboundMessage

CONFIG = GmailMailboxConfig(
    email_address="user@gmail.com",
    access_token="access-token",
    refresh_token="refresh-token",
)
CTX = MailboxContext(connector_type="gmail", config=CONFIG, user_id=1)


def _raw_email_bytes() -> bytes:
    message = EmailMessage()
    message["From"] = "hr@company.test"
    message["To"] = "user@gmail.com"
    message["Subject"] = "Follow up"
    message.set_content("Hello there")
    return message.as_bytes()


@respx.mock
def test_fetch_messages_parses_inbox() -> None:
    gmail_id = "18c5f2a3b4d6e7f8"
    raw = base64.urlsafe_b64encode(_raw_email_bytes()).decode("ascii")
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages").mock(
        return_value=Response(200, json={"messages": [{"id": gmail_id}]})
    )
    respx.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{gmail_id}").mock(
        return_value=Response(200, json={"raw": raw})
    )
    result = GmailMailbox().fetch_messages(CTX, limit=10)
    assert len(result.messages) == 1
    assert result.messages[0].uid == gmail_id_to_uid(gmail_id)
    assert result.messages[0].subject == "Follow up"


@respx.mock
def test_send_message_posts_raw_payload() -> None:
    route = respx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send").mock(
        return_value=Response(200, json={"id": "sent"})
    )
    result = GmailMailbox().send_message(
        CTX,
        OutboundMessage(to=["hr@company.test"], subject="Re: Role", body="Thanks!"),
    )
    assert result.status == "sent"
    assert route.called


@respx.mock
def test_move_message_applies_label() -> None:
    uid = gmail_id_to_uid("18c5f2a3b4d6e7f8")
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/labels").mock(
        return_value=Response(
            200,
            json={"labels": [{"id": "Label_1", "name": "HeadStart/General"}]},
        )
    )
    route = respx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/18c5f2a3b4d6e7f8/modify"
    ).mock(return_value=Response(200, json={"id": "18c5f2a3b4d6e7f8"}))
    result = GmailMailbox().move_message(CTX, uid=uid, destination="HeadStart/General")
    assert result.status == "moved"
    assert route.called
    assert route.calls.last.request.content
    assert b"Label_1" in route.calls.last.request.content
