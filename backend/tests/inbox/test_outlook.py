"""Tests for the Outlook mailbox adapter (mocked Microsoft Graph)."""

from datetime import UTC, datetime
from email.message import EmailMessage

import respx
from httpx import Response

from app.inbox.adapters.outlook import OutlookMailbox
from app.inbox.outlook_ids import outlook_message_uid
from app.inbox.types import MailboxContext, OutboundMessage, OutlookMailboxConfig

CONFIG = OutlookMailboxConfig(
    email_address="user@outlook.test",
    access_token="access-token",
    refresh_token="refresh-token",
)
CTX = MailboxContext(connector_type="outlook", config=CONFIG, user_id=1)
GRAPH_ID = "AAMkAGI2TG93AAA="
RECEIVED_AT = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def _raw_email_bytes() -> bytes:
    message = EmailMessage()
    message["From"] = "hr@company.test"
    message["To"] = "user@outlook.test"
    message["Subject"] = "Follow up"
    message.set_content("Hello there")
    return message.as_bytes()


@respx.mock
def test_fetch_messages_parses_inbox() -> None:
    respx.get("https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages").mock(
        return_value=Response(
            200,
            json={
                "value": [
                    {
                        "id": GRAPH_ID,
                        "receivedDateTime": RECEIVED_AT.isoformat().replace("+00:00", "Z"),
                    }
                ]
            },
        )
    )
    respx.get(f"https://graph.microsoft.com/v1.0/me/messages/{GRAPH_ID}/$value").mock(
        return_value=Response(200, content=_raw_email_bytes())
    )
    result = OutlookMailbox().fetch_messages(CTX, limit=10)
    assert len(result.messages) == 1
    assert result.messages[0].uid == outlook_message_uid(GRAPH_ID, RECEIVED_AT)
    assert result.messages[0].subject == "Follow up"
    assert result.messages[0].raw_headers["x-ms-graph-id"] == GRAPH_ID


@respx.mock
def test_send_message_posts_send_mail() -> None:
    route = respx.post("https://graph.microsoft.com/v1.0/me/sendMail").mock(
        return_value=Response(202)
    )
    result = OutlookMailbox().send_message(
        CTX,
        OutboundMessage(to=["hr@company.test"], subject="Re: Role", body="Thanks!"),
    )
    assert result.status == "sent"
    assert route.called


@respx.mock
def test_move_message_uses_graph_folder() -> None:
    uid = outlook_message_uid(GRAPH_ID, RECEIVED_AT)
    respx.get("https://graph.microsoft.com/v1.0/me/mailFolders").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "folder-root", "displayName": "HeadStart"}]},
        )
    )
    respx.get("https://graph.microsoft.com/v1.0/me/mailFolders/folder-root/childFolders").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "folder-general", "displayName": "General"}]},
        )
    )
    route = respx.post(f"https://graph.microsoft.com/v1.0/me/messages/{GRAPH_ID}/move").mock(
        return_value=Response(200, json={"id": GRAPH_ID})
    )
    result = OutlookMailbox().move_message(
        CTX,
        uid=uid,
        destination="HeadStart/General",
        provider_message_id=GRAPH_ID,
    )
    assert result.status == "moved"
    assert route.called
