"""Tests for the IMAP + SMTP mailbox connector (mocked network I/O)."""

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from app.inbox.adapters.imap_smtp import ImapSmtpMailbox
from app.inbox.types import MailboxConfig, MailboxContext, OutboundMessage

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


def _sample_raw_email() -> bytes:
    msg = EmailMessage()
    msg["From"] = "hr@company.test"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Interview follow-up"
    msg["Message-ID"] = "<abc@company.test>"
    msg.set_content("Please reply with your availability.")
    return msg.as_bytes()


def test_fetch_messages_parses_uid_results() -> None:
    raw = _sample_raw_email()
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"1 2"]),
        ("OK", [(b"1 (RFC822)", raw)]),
        ("OK", [(b"2 (RFC822)", raw)]),
    ]

    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().fetch_messages(CTX, limit=10)

    assert len(result.messages) == 2
    assert result.messages[0].subject == "Interview follow-up"
    assert result.messages[0].from_addr == "hr@company.test"
    assert result.max_uid == 2
    mock_client.login.assert_called_once_with(CONFIG.imap_user, CONFIG.imap_password)
    mock_client.select.assert_called_with(CONFIG.imap_mailbox, readonly=True)


def test_fetch_messages_honors_since_uid() -> None:
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"5 6 7"]),
        ("OK", []),
    ]

    with patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_client):
        result = ImapSmtpMailbox().fetch_messages(CTX, since_uid=6, limit=10)

    mock_client.uid.assert_any_call("search", "UID 7:*")
    assert result.messages == []
    assert result.max_uid == 6


def test_send_message_uses_smtp() -> None:
    mock_smtp = MagicMock()
    with patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp):
        result = ImapSmtpMailbox().send_message(
            CTX,
            OutboundMessage(
                to=["recruiter@company.test"],
                subject="Re: Interview",
                body="I am free Tuesday afternoon.",
                in_reply_to="<abc@company.test>",
            ),
        )

    assert result.status == "sent"
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.send_message.assert_called_once()
    mock_smtp.quit.assert_called_once()


def test_test_connection_checks_imap_and_smtp() -> None:
    mock_imap = MagicMock()
    mock_smtp = MagicMock()
    with (
        patch("app.inbox.adapters.imap_smtp.imaplib.IMAP4_SSL", return_value=mock_imap),
        patch("app.inbox.adapters.imap_smtp.smtplib.SMTP", return_value=mock_smtp),
    ):
        result = ImapSmtpMailbox().test_connection(CTX)

    assert result.imap_ok is True
    assert result.smtp_ok is True
    assert result.error is None
    mock_smtp.noop.assert_called_once()
