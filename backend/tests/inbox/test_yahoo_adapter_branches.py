"""Branch coverage for the Yahoo adapter (search/fetch/move/error paths)."""

import imaplib
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.inbox.adapters.yahoo import YahooMailbox
from app.inbox.types import GmailMailboxConfig, MailboxContext, OutboundMessage, YahooMailboxConfig

CONFIG = YahooMailboxConfig(
    email_address="user@yahoo.test", access_token="access-token", refresh_token="refresh-token"
)
CTX = MailboxContext(connector_type="yahoo", config=CONFIG, user_id=1)


def _raw_email() -> bytes:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "hr@company.test"
    msg["To"] = "user@yahoo.test"
    msg["Subject"] = "Interview"
    msg.set_content("hello")
    return msg.as_bytes()


# --------------------------------------------------------------------------- #
# config guards
# --------------------------------------------------------------------------- #


def test_config_rejects_wrong_connector_type() -> None:
    ctx = MailboxContext(connector_type="gmail", config=CONFIG, user_id=1)
    with pytest.raises(TypeError, match="connector_type='yahoo'"):
        YahooMailbox().send_message(ctx, OutboundMessage(to=["x@y"], subject="S", body="B"))


def test_config_rejects_wrong_config_type() -> None:
    ctx = MailboxContext(
        connector_type="yahoo",
        config=GmailMailboxConfig(email_address="u@x.test", access_token="a", refresh_token="r"),
        user_id=1,
    )
    with pytest.raises(TypeError, match="YahooMailboxConfig"):
        YahooMailbox().send_message(ctx, OutboundMessage(to=["x@y"], subject="S", body="B"))


# --------------------------------------------------------------------------- #
# fetch branches
# --------------------------------------------------------------------------- #


def test_fetch_returns_empty_when_search_not_ok() -> None:
    mock_client = MagicMock()
    mock_client.uid.return_value = ("NO", [b""])
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().fetch_messages(CTX, since_uid=5, limit=10)
    assert result.messages == []
    assert result.max_uid == 5
    # since_uid path builds "UID 6:*"
    mock_client.uid.assert_any_call("search", "UID 6:*")


def test_fetch_skips_bad_fetch_results() -> None:
    raw = _raw_email()
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1 2 3"]),
        ("NO", None),  # uid 1: status not OK -> skip
        ("OK", [None]),  # uid 2: fetched[0] is None -> skip
        ("OK", [(b"3 (RFC822)", raw)]),  # uid 3: ok
    ]
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().fetch_messages(CTX, limit=10)
    assert [m.uid for m in result.messages] == [3]


def test_fetch_skips_non_bytes_payload() -> None:
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1"]),
        ("OK", [(b"1 (RFC822)", "not-bytes")]),  # payload not bytes -> skip
    ]
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().fetch_messages(CTX, limit=10)
    assert result.messages == []


def test_fetch_zero_limit_keeps_all() -> None:
    raw = _raw_email()
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1 2"]),
        ("OK", [(b"1 (RFC822)", raw)]),
        ("OK", [(b"2 (RFC822)", raw)]),
    ]
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().fetch_messages(CTX, limit=0)
    assert len(result.messages) == 2


# --------------------------------------------------------------------------- #
# send failure
# --------------------------------------------------------------------------- #


def test_send_failure_returns_failed() -> None:
    mock_smtp = MagicMock()
    mock_smtp.send_message.side_effect = smtplib.SMTPException("boom")
    with patch("app.inbox.adapters.yahoo.smtplib.SMTP", return_value=mock_smtp):
        result = YahooMailbox().send_message(
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
# test_connection error paths
# --------------------------------------------------------------------------- #


def test_send_invokes_smtp_auth_callback() -> None:
    # Drive smtp.auth so the OAUTHBEARER auth_response callback actually runs,
    # covering the inner `return auth_bytes` line.
    mock_smtp = MagicMock()

    def fake_auth(mechanism, authobject, *, initial_response_ok=True):
        assert authobject(None)  # invoke the callback -> returns auth bytes

    mock_smtp.auth.side_effect = fake_auth
    with patch("app.inbox.adapters.yahoo.smtplib.SMTP", return_value=mock_smtp):
        result = YahooMailbox().send_message(
            CTX, OutboundMessage(to=["hr@x"], subject="S", body="B")
        )
    assert result.status == "sent"


def test_test_connection_skips_logout_when_connect_fails() -> None:
    # IMAP4_SSL constructor raises -> client stays None -> the `if client is not
    # None` guard in the finally block takes the false branch (116->118).
    mock_smtp = MagicMock()
    with (
        patch(
            "app.inbox.adapters.yahoo.imaplib.IMAP4_SSL",
            side_effect=OSError("connect refused"),
        ),
        patch("app.inbox.adapters.yahoo.smtplib.SMTP", return_value=mock_smtp),
    ):
        result = YahooMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.smtp_ok is True
    assert "IMAP:" in (result.error or "")


def test_test_connection_reports_both_failures() -> None:
    mock_imap = MagicMock()
    mock_imap.select.side_effect = imaplib.IMAP4.error("imap down")
    mock_smtp = MagicMock()
    mock_smtp.noop.side_effect = smtplib.SMTPException("smtp down")
    with (
        patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_imap),
        patch("app.inbox.adapters.yahoo.smtplib.SMTP", return_value=mock_smtp),
    ):
        result = YahooMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.smtp_ok is False
    assert "IMAP:" in (result.error or "")
    assert "SMTP:" in (result.error or "")


# --------------------------------------------------------------------------- #
# move branches
# --------------------------------------------------------------------------- #


def test_move_to_inbox_is_skipped() -> None:
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL") as mock_ssl:
        result = YahooMailbox().move_message(CTX, uid=1, destination="Inbox")
    assert result.status == "skipped"
    mock_ssl.assert_not_called()


def test_move_falls_back_to_copy_delete() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)  # no MOVE
    mock_client.uid.side_effect = [
        ("OK", None),  # COPY
        ("OK", None),  # STORE
    ]
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "moved"
    mock_client.expunge.assert_called_once()


def test_move_copy_failure_returns_failed() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)
    mock_client.uid.side_effect = [("NO", None)]  # COPY fails
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "failed"
    assert "COPY" in (result.error or "")


def test_move_store_failure_returns_failed() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)
    mock_client.uid.side_effect = [("OK", None), ("NO", None)]  # COPY ok, STORE fails
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "failed"
    assert "STORE" in (result.error or "")


def test_move_imap_error_returns_failed() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)
    mock_client.select.side_effect = imaplib.IMAP4.error("boom")
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "failed"
    assert result.error


def test_move_uid_move_capabilities_none() -> None:
    # capabilities is falsy -> normalized set empty -> MOVE unsupported -> fallback.
    mock_client = MagicMock()
    mock_client.capabilities = None
    mock_client.uid.side_effect = [("OK", None), ("OK", None)]
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "moved"


def test_move_uid_move_with_str_capabilities() -> None:
    # A non-bytes capability entry exercises the str(cap) branch in _uid_move.
    mock_client = MagicMock()
    mock_client.capabilities = ("MOVE",)  # str, not bytes
    mock_client.uid.return_value = ("OK", None)
    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "moved"
    mock_client.uid.assert_called_with("MOVE", "3", "HeadStart/General")
