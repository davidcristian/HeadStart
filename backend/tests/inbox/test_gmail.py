"""Tests for the Gmail mailbox adapter (mocked Gmail API)."""

import base64
from datetime import UTC, datetime
from email.message import EmailMessage

import respx
from httpx import Response

from app.inbox.adapters.gmail import GMAIL_ID_HEADER, GmailMailbox
from app.inbox.gmail_ids import gmail_message_uid
from app.inbox.types import GmailMailboxConfig, MailboxContext, OutboundMessage

CONFIG = GmailMailboxConfig(
    email_address="user@gmail.com",
    access_token="access-token",
    refresh_token="refresh-token",
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


def _mock_message(gmail_id: str, received_at: datetime) -> None:
    # The internalDate probe (format=minimal) and the raw fetch (format=raw) both
    # GET this URL; one mock serving both fields satisfies each call.
    millis = str(int(received_at.timestamp() * 1000))
    respx.get(f"{BASE}/messages/{gmail_id}").mock(
        return_value=Response(200, json={"internalDate": millis, "raw": _raw_b64()})
    )


@respx.mock
def test_fetch_messages_parses_inbox() -> None:
    gmail_id = "18c5f2a3b4d6e7f8"
    received_at = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    respx.get(f"{BASE}/messages").mock(
        return_value=Response(200, json={"messages": [{"id": gmail_id}]})
    )
    _mock_message(gmail_id, received_at)
    result = GmailMailbox().fetch_messages(CTX, limit=10)
    assert len(result.messages) == 1
    assert result.messages[0].uid == gmail_message_uid(gmail_id, received_at)
    assert result.messages[0].subject == "Follow up"
    assert result.messages[0].raw_headers[GMAIL_ID_HEADER] == gmail_id


@respx.mock
def test_fetch_orders_by_received_time_not_hex_id() -> None:
    """Gmail lists newest-first and ids are not chronological: order by received time."""
    older_id = "ffffffffffffffff"  # large hex, but received earlier
    newer_id = "0000000000000001"  # tiny hex, but received later
    older_at = datetime(2026, 6, 1, tzinfo=UTC)
    newer_at = datetime(2026, 6, 30, tzinfo=UTC)
    respx.get(f"{BASE}/messages").mock(
        return_value=Response(200, json={"messages": [{"id": newer_id}, {"id": older_id}]})
    )
    _mock_message(older_id, older_at)
    _mock_message(newer_id, newer_at)
    result = GmailMailbox().fetch_messages(CTX, limit=10)
    assert [m.uid for m in result.messages] == [
        gmail_message_uid(older_id, older_at),
        gmail_message_uid(newer_id, newer_at),
    ]


@respx.mock
def test_fetch_short_circuits_date_probes_at_limit() -> None:
    """List may return many ids; only probe internalDate for the oldest `limit`."""
    # Newest-first listing: n0 is newest, n4 is oldest. limit=2 should date-probe
    # only n4 then n3 (and raw-fetch those two). It must skip n0/n1/n2.
    ids_newest_first = [f"n{i}" for i in range(5)]
    respx.get(f"{BASE}/messages").mock(
        return_value=Response(200, json={"messages": [{"id": gid} for gid in ids_newest_first]})
    )
    routes = {}
    for i, gid in enumerate(ids_newest_first):
        # n0 newest (+4 days) … n4 oldest (+0 days)
        received = datetime(2026, 6, 1 + (4 - i), tzinfo=UTC)
        millis = str(int(received.timestamp() * 1000))
        routes[gid] = respx.get(f"{BASE}/messages/{gid}").mock(
            return_value=Response(200, json={"internalDate": millis, "raw": _raw_b64()})
        )
    result = GmailMailbox().fetch_messages(CTX, limit=2)
    assert [m.raw_headers.get("x-gmail-id") for m in result.messages] == ["n4", "n3"]
    assert routes["n4"].call_count >= 1  # minimal + raw
    assert routes["n3"].call_count >= 1
    assert routes["n0"].call_count == 0
    assert routes["n1"].call_count == 0
    assert routes["n2"].call_count == 0


@respx.mock
def test_fetch_does_not_skip_newer_mail_with_smaller_id() -> None:
    """Regression: a later-arriving message whose id sorts below the cursor's era must
    not be skipped (the old int(hex) uid ordered by id value, not received time)."""
    new_id = "01"  # tiny hex value
    received_at = datetime(2026, 6, 30, tzinfo=UTC)
    since_uid = gmail_message_uid("deadbeef", datetime(2026, 1, 1, tzinfo=UTC))
    respx.get(f"{BASE}/messages").mock(
        return_value=Response(200, json={"messages": [{"id": new_id}]})
    )
    _mock_message(new_id, received_at)
    result = GmailMailbox().fetch_messages(CTX, since_uid=since_uid, limit=10)
    assert len(result.messages) == 1
    uid = gmail_message_uid(new_id, received_at)
    assert result.messages[0].uid == uid
    assert uid > since_uid
    assert result.max_uid == uid


@respx.mock
def test_send_message_posts_raw_payload() -> None:
    route = respx.post(f"{BASE}/messages/send").mock(
        return_value=Response(200, json={"id": "sent"})
    )
    result = GmailMailbox().send_message(
        CTX,
        OutboundMessage(to=["hr@company.test"], subject="Re: Role", body="Thanks!"),
    )
    assert result.status == "sent"
    assert route.called


@respx.mock
def test_move_message_uses_provider_message_id() -> None:
    gmail_id = "18c5f2a3b4d6e7f8"
    uid = gmail_message_uid(gmail_id, datetime(2026, 6, 30, tzinfo=UTC))
    respx.get(f"{BASE}/labels").mock(
        return_value=Response(
            200, json={"labels": [{"id": "Label_1", "name": "HeadStart/General"}]}
        )
    )
    route = respx.post(f"{BASE}/messages/{gmail_id}/modify").mock(
        return_value=Response(200, json={"id": gmail_id})
    )
    result = GmailMailbox().move_message(
        CTX, uid=uid, destination="HeadStart/General", provider_message_id=gmail_id
    )
    assert result.status == "moved"
    assert route.called
    assert b"Label_1" in route.calls.last.request.content


@respx.mock
def test_move_message_without_provider_id_fails() -> None:
    result = GmailMailbox().move_message(CTX, uid=123, destination="HeadStart/General")
    assert result.status == "failed"
    assert "gmail_message_id" in (result.error or "")
