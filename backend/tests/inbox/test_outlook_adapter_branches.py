"""Branch coverage for the Outlook adapter (guards, folder creation, errors)."""

from datetime import UTC, datetime
from email.message import EmailMessage

import pytest
import respx
from httpx import Response

from app.inbox.adapters.outlook import OutlookMailbox, _parse_graph_datetime
from app.inbox.outlook_ids import outlook_message_uid
from app.inbox.types import (
    GmailMailboxConfig,
    MailboxContext,
    OutboundMessage,
    OutlookMailboxConfig,
)

CONFIG = OutlookMailboxConfig(
    email_address="user@outlook.test", access_token="access-token", refresh_token="refresh-token"
)
CTX = MailboxContext(connector_type="outlook", config=CONFIG, user_id=1)
GRAPH = "https://graph.microsoft.com/v1.0"
INBOX_MSGS = f"{GRAPH}/me/mailFolders/inbox/messages"


def _raw_bytes() -> bytes:
    message = EmailMessage()
    message["From"] = "hr@company.test"
    message["To"] = "user@outlook.test"
    message["Subject"] = "Follow up"
    message.set_content("Hello there")
    return message.as_bytes()


# --------------------------------------------------------------------------- #
# helpers + config guards
# --------------------------------------------------------------------------- #


def test_parse_graph_datetime_variants() -> None:
    assert _parse_graph_datetime(123) is None
    assert _parse_graph_datetime("") is None
    assert _parse_graph_datetime("not-a-date") is None
    parsed = _parse_graph_datetime("2026-06-30T12:00:00Z")
    assert parsed == datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def test_config_rejects_wrong_connector_type() -> None:
    ctx = MailboxContext(connector_type="gmail", config=CONFIG, user_id=1)
    with pytest.raises(TypeError, match="connector_type='outlook'"):
        OutlookMailbox().fetch_messages(ctx)


def test_config_rejects_wrong_config_type() -> None:
    ctx = MailboxContext(
        connector_type="outlook",
        config=GmailMailboxConfig(email_address="u@x.test", access_token="a", refresh_token="r"),
        user_id=1,
    )
    with pytest.raises(TypeError, match="OutlookMailboxConfig"):
        OutlookMailbox().fetch_messages(ctx)


# --------------------------------------------------------------------------- #
# fetch branches
# --------------------------------------------------------------------------- #


@respx.mock
def test_fetch_skips_bad_entries_and_applies_since_filter() -> None:
    good_id = "AAA-good"
    received = datetime(2026, 6, 30, tzinfo=UTC)
    since_uid = 1  # triggers the $filter branch (line 54-55)
    respx.get(INBOX_MSGS).mock(
        return_value=Response(
            200,
            json={
                "value": [
                    "not-a-dict",
                    {"id": ""},
                    {
                        "id": good_id,
                        "receivedDateTime": received.isoformat().replace("+00:00", "Z"),
                    },
                ]
            },
        )
    )
    respx.get(f"{GRAPH}/me/messages/{good_id}/$value").mock(
        return_value=Response(200, content=_raw_bytes())
    )
    result = OutlookMailbox().fetch_messages(CTX, since_uid=since_uid, limit=10)
    assert [m.raw_headers.get("x-ms-graph-id") for m in result.messages] == [good_id]


@respx.mock
def test_fetch_skips_uid_at_or_below_cursor() -> None:
    gid = "AAA-old"
    received = datetime(2026, 1, 1, tzinfo=UTC)
    since_uid = outlook_message_uid(gid, received)
    respx.get(INBOX_MSGS).mock(
        return_value=Response(
            200,
            json={
                "value": [
                    {"id": gid, "receivedDateTime": received.isoformat().replace("+00:00", "Z")}
                ]
            },
        )
    )
    result = OutlookMailbox().fetch_messages(CTX, since_uid=since_uid, limit=10)
    assert result.messages == []


@respx.mock
def test_fetch_skips_when_raw_unavailable() -> None:
    gid = "AAA-raw-missing"
    received = datetime(2026, 6, 30, tzinfo=UTC)
    respx.get(INBOX_MSGS).mock(
        return_value=Response(
            200,
            json={
                "value": [
                    {"id": gid, "receivedDateTime": received.isoformat().replace("+00:00", "Z")}
                ]
            },
        )
    )
    respx.get(f"{GRAPH}/me/messages/{gid}/$value").mock(return_value=Response(404))
    assert OutlookMailbox().fetch_messages(CTX, limit=10).messages == []


@respx.mock
def test_fetch_stops_at_limit() -> None:
    received = datetime(2026, 6, 30, tzinfo=UTC)
    ts = received.isoformat().replace("+00:00", "Z")
    respx.get(INBOX_MSGS).mock(
        return_value=Response(
            200,
            json={
                "value": [
                    {"id": "m1", "receivedDateTime": ts},
                    {"id": "m2", "receivedDateTime": ts},
                    {"id": "m3", "receivedDateTime": ts},
                ]
            },
        )
    )
    for gid in ("m1", "m2", "m3"):
        respx.get(f"{GRAPH}/me/messages/{gid}/$value").mock(
            return_value=Response(200, content=_raw_bytes())
        )
    result = OutlookMailbox().fetch_messages(CTX, limit=2)
    assert len(result.messages) == 2


# --------------------------------------------------------------------------- #
# send
# --------------------------------------------------------------------------- #


@respx.mock
def test_send_with_headers_success() -> None:
    route = respx.post(f"{GRAPH}/me/sendMail").mock(return_value=Response(202))
    result = OutlookMailbox().send_message(
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
    assert result.status == "sent"
    assert route.called


@respx.mock
def test_send_failure_returns_failed() -> None:
    respx.post(f"{GRAPH}/me/sendMail").mock(return_value=Response(500))
    result = OutlookMailbox().send_message(CTX, OutboundMessage(to=["hr@x"], subject="S", body="B"))
    assert result.status == "failed"
    assert result.error


# --------------------------------------------------------------------------- #
# test_connection
# --------------------------------------------------------------------------- #


@respx.mock
def test_test_connection_success() -> None:
    respx.get(f"{GRAPH}/me").mock(return_value=Response(200, json={"mail": "user@outlook.test"}))
    result = OutlookMailbox().test_connection(CTX)
    assert result.imap_ok is True
    assert result.smtp_ok is True


@respx.mock
def test_test_connection_email_mismatch() -> None:
    respx.get(f"{GRAPH}/me").mock(
        return_value=Response(200, json={"userPrincipalName": "other@outlook.test"})
    )
    result = OutlookMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert "does not match" in (result.error or "")


@respx.mock
def test_test_connection_http_error() -> None:
    respx.get(f"{GRAPH}/me").mock(return_value=Response(500))
    result = OutlookMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.error


# --------------------------------------------------------------------------- #
# move / folder resolution
# --------------------------------------------------------------------------- #


def test_move_without_provider_id_fails() -> None:
    result = OutlookMailbox().move_message(CTX, uid=1, destination="HeadStart/General")
    assert result.status == "failed"
    assert "graph_message_id" in (result.error or "")


@respx.mock
def test_move_creates_nested_folders() -> None:
    gid = "AAA-move"
    # Root list has no HeadStart -> create it; child list empty -> create General.
    respx.get(f"{GRAPH}/me/mailFolders").mock(
        return_value=Response(200, json={"value": [{"id": "other", "displayName": "Other"}]})
    )
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": "hs-id"}))
    respx.get(f"{GRAPH}/me/mailFolders/hs-id/childFolders").mock(
        return_value=Response(200, json={"value": []})
    )
    respx.post(f"{GRAPH}/me/mailFolders/hs-id/childFolders").mock(
        return_value=Response(200, json={"id": "gen-id"})
    )
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart/General", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_empty_destination_fails() -> None:
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="   /  ", provider_message_id="g1"
    )
    assert result.status == "failed"
    assert "Could not create Outlook folder" in (result.error or "")


@respx.mock
def test_move_folder_create_failure_fails() -> None:
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"value": []}))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(400))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id="g1"
    )
    assert result.status == "failed"
    assert "Could not create Outlook folder" in (result.error or "")


@respx.mock
def test_move_folder_create_non_str_id_fails() -> None:
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"value": []}))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": 123}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id="g1"
    )
    assert result.status == "failed"


@respx.mock
def test_move_list_folders_error_and_non_list() -> None:
    # First-level list returns 400 -> [] folders -> create; created id used to move.
    gid = "AAA-listerr"
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(400))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": "hs2"}))
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_list_folders_non_list_payload() -> None:
    gid = "AAA-nonlist"
    respx.get(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"value": "nope"}))
    respx.post(f"{GRAPH}/me/mailFolders").mock(return_value=Response(200, json={"id": "hs3"}))
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_folders_with_non_dict_entries_and_existing_match() -> None:
    gid = "AAA-existing"
    respx.get(f"{GRAPH}/me/mailFolders").mock(
        return_value=Response(
            200,
            json={"value": ["not-a-dict", {"id": "hs-existing", "displayName": "HeadStart"}]},
        )
    )
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(200, json={"id": gid}))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "moved"


@respx.mock
def test_move_graph_http_error_returns_failed() -> None:
    gid = "AAA-moveerr"
    respx.get(f"{GRAPH}/me/mailFolders").mock(
        return_value=Response(200, json={"value": [{"id": "hs", "displayName": "HeadStart"}]})
    )
    respx.post(f"{GRAPH}/me/messages/{gid}/move").mock(return_value=Response(500))
    result = OutlookMailbox().move_message(
        CTX, uid=1, destination="HeadStart", provider_message_id=gid
    )
    assert result.status == "failed"
    assert result.error
