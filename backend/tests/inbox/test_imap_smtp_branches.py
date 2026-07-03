"""Branch coverage for the IMAP/SMTP adapter (config, error, connect variants)."""

import imaplib
import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from app.inbox.adapters.imap_smtp import ImapSmtpMailbox
from app.inbox.types import GmailMailboxConfig, MailboxConfig, MailboxContext, OutboundMessage

CONFIG = MailboxConfig(
    imap_host="imap.example.com",
    imap_port=993,
    imap_user="user@example.com",
    imap_password="imap-secret",
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_from="user@example.com",
)
CTX = MailboxContext(connector_type="imap_smtp", config=CONFIG, user_id=1)


def _raw_email() -> bytes:
    msg = EmailMessage()
    msg["From"] = "hr@company.test"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Interview"
    msg.set_content("hello")
    return msg.as_bytes()


# --------------------------------------------------------------------------- #
# config guard
# --------------------------------------------------------------------------- #


def test_config_rejects_wrong_config_type() -> None:
    ctx = MailboxContext(
        connector_type="imap_smtp",
        config=GmailMailboxConfig(email_address="u@x.test", access_token="a", refresh_token="r"),
        user_id=1,
    )
    with pytest.raises(TypeError, match="imap_smtp connector requires MailboxConfig"):
        ImapSmtpMailbox().send_message(ctx, OutboundMessage(to=["x@y"], subject="S", body="B"))


# --------------------------------------------------------------------------- #
# fetch branches
# --------------------------------------------------------------------------- #


def test_fetch_returns_empty_when_search_not_ok() -> None:
    mock_client = MagicMock()
    mock_client.uid.return_value = ("NO", None)
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().fetch_messages(CTX, limit=10)
    assert result.messages == []
    assert result.max_uid is None


def test_fetch_skips_bad_fetch_results() -> None:
    raw = _raw_email()
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1 2 3"]),
        ("NO", None),  # uid 1: status not OK -> skip (line 71)
        ("OK", [None]),  # uid 2: fetched[0] is None -> skip
        ("OK", [(b"3 (RFC822)", raw)]),  # uid 3: ok
    ]
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().fetch_messages(CTX, limit=10)
    assert [m.uid for m in result.messages] == [3]


def test_fetch_skips_non_bytes_payload() -> None:
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1"]),
        ("OK", [(b"1 (RFC822)", "not-bytes")]),
    ]
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().fetch_messages(CTX, limit=10)
    assert result.messages == []


def test_fetch_zero_limit_keeps_all() -> None:
    raw = _raw_email()
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1 2"]),
        ("OK", [(b"1 (RFC822)", raw)]),
        ("OK", [(b"2 (RFC822)", raw)]),
    ]
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().fetch_messages(CTX, limit=0)
    assert len(result.messages) == 2


# --------------------------------------------------------------------------- #
# send branches
# --------------------------------------------------------------------------- #


def test_send_with_all_headers_success() -> None:
    mock_smtp = MagicMock()
    with patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp):
        result = ImapSmtpMailbox().send_message(
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


def test_send_failure_returns_failed() -> None:
    mock_smtp = MagicMock()
    mock_smtp.send_message.side_effect = smtplib.SMTPException("boom")
    with patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp):
        result = ImapSmtpMailbox().send_message(
            CTX, OutboundMessage(to=["hr@x"], subject="S", body="B")
        )
    assert result.status == "failed"
    assert result.error


# --------------------------------------------------------------------------- #
# test_connection error paths
# --------------------------------------------------------------------------- #


def test_test_connection_reports_both_failures() -> None:
    mock_imap = MagicMock()
    mock_imap.select.side_effect = imaplib.IMAP4.error("imap down")
    mock_smtp = MagicMock()
    mock_smtp.noop.side_effect = smtplib.SMTPException("smtp down")
    with (
        patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_imap),
        patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp),
    ):
        result = ImapSmtpMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.smtp_ok is False
    assert "IMAP:" in (result.error or "")
    assert "SMTP:" in (result.error or "")


def test_test_connection_skips_logout_when_connect_fails() -> None:
    mock_smtp = MagicMock()
    with (
        patch(
            "app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL",
            side_effect=OSError("connect refused"),
        ),
        patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp),
    ):
        result = ImapSmtpMailbox().test_connection(CTX)
    assert result.imap_ok is False
    assert result.smtp_ok is True


# --------------------------------------------------------------------------- #
# move branches
# --------------------------------------------------------------------------- #


def test_move_copy_failure_returns_failed() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)
    mock_client.uid.side_effect = [("NO", None)]  # COPY fails
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "failed"
    assert "COPY" in (result.error or "")


def test_move_store_failure_returns_failed() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)
    mock_client.uid.side_effect = [("OK", None), ("NO", None)]  # COPY ok, STORE fails
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "failed"
    assert "STORE" in (result.error or "")


def test_move_imap_error_returns_failed() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1",)
    mock_client.select.side_effect = imaplib.IMAP4.error("boom")
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().move_message(CTX, uid=3, destination="HeadStart/General")
    assert result.status == "failed"
    assert result.error


# --------------------------------------------------------------------------- #
# connection variants: non-SSL IMAP, SMTP without TLS / without user
# --------------------------------------------------------------------------- #


def test_fetch_uses_plain_imap4_when_ssl_disabled() -> None:
    config = CONFIG.model_copy(update={"imap_use_ssl": False})
    ctx = MailboxContext(connector_type="imap_smtp", config=config, user_id=1)
    mock_client = MagicMock()
    mock_client.uid.return_value = ("NO", None)
    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4", return_value=mock_client) as ctor:
        ImapSmtpMailbox().fetch_messages(ctx, limit=10)
    ctor.assert_called_once()
    mock_client.login.assert_called_once()


def test_send_without_tls_still_logs_in_with_imap_fallback() -> None:
    # smtp_use_tls False -> starttls skipped (branch 214->216); smtp_user falls back
    # to imap_user so login IS called.
    config = MailboxConfig(
        imap_host="imap.example.com",
        imap_user="onlyimap",
        imap_password="pw",
        smtp_host="smtp.example.com",
        smtp_use_tls=False,
        smtp_user="",
        smtp_password="",
    )
    ctx = MailboxContext(connector_type="imap_smtp", config=config, user_id=1)
    mock_smtp = MagicMock()
    with patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp):
        result = ImapSmtpMailbox().send_message(
            ctx, OutboundMessage(to=["hr@x"], subject="S", body="B")
        )
    assert result.status == "sent"
    mock_smtp.starttls.assert_not_called()
    mock_smtp.login.assert_called_once()


def test_send_skips_login_when_no_smtp_user_resolvable() -> None:
    # Both smtp_user and imap_user empty -> smtp_user falsy -> login skipped
    # (branch 218->220). imap_user has min_length=1 so bypass validation with
    # model_construct to reach the guard.
    config = MailboxConfig.model_construct(
        imap_host="imap.example.com",
        imap_port=993,
        imap_use_ssl=True,
        imap_user="",
        imap_password="pw",
        imap_mailbox="INBOX",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_use_tls=True,
        smtp_user="",
        smtp_password="",
        smtp_from="from@example.com",
    )
    ctx = MailboxContext(connector_type="imap_smtp", config=config, user_id=1)
    mock_smtp = MagicMock()
    with patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp):
        result = ImapSmtpMailbox().send_message(
            ctx, OutboundMessage(to=["hr@x"], subject="S", body="B")
        )
    assert result.status == "sent"
    mock_smtp.login.assert_not_called()
