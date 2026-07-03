"""Tests for the Yahoo mailbox adapter (mocked IMAP/SMTP)."""

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from app.inbox.adapters.yahoo import YahooMailbox
from app.inbox.types import MailboxContext, OutboundMessage, YahooMailboxConfig

CONFIG = YahooMailboxConfig(
    email_address="user@yahoo.test",
    access_token="access-token",
    refresh_token="refresh-token",
)
CTX = MailboxContext(connector_type="yahoo", config=CONFIG, user_id=1)


def _sample_raw_email() -> bytes:
    msg = EmailMessage()
    msg["From"] = "hr@company.test"
    msg["To"] = "user@yahoo.test"
    msg["Subject"] = "Interview follow-up"
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

    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().fetch_messages(CTX, limit=10)

    assert len(result.messages) == 2
    assert result.messages[0].subject == "Interview follow-up"
    assert result.max_uid == 2
    mock_client.authenticate.assert_called_once()
    mock_client.select.assert_called_with("Inbox", readonly=True)


def test_fetch_messages_returns_oldest_unprocessed_when_over_limit() -> None:
    """Regression: must not skip older UIDs when more than `limit` messages are pending."""
    raw = _sample_raw_email()
    mock_client = MagicMock()
    mock_client.uid.side_effect = [
        ("OK", [b"201 202 203"]),
        ("OK", [(b"201 (RFC822)", raw)]),
        ("OK", [(b"202 (RFC822)", raw)]),
    ]

    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().fetch_messages(CTX, since_uid=200, limit=2)

    assert [message.uid for message in result.messages] == [201, 202]
    assert result.max_uid == 202


def test_send_message_uses_smtp() -> None:
    mock_smtp = MagicMock()
    with patch("app.inbox.adapters.yahoo.smtplib.SMTP", return_value=mock_smtp):
        result = YahooMailbox().send_message(
            CTX,
            OutboundMessage(
                to=["recruiter@company.test"],
                subject="Re: Interview",
                body="I am free Tuesday afternoon.",
            ),
        )

    assert result.status == "sent"
    mock_smtp.starttls.assert_called_once()
    mock_smtp.auth.assert_called_once()
    mock_smtp.send_message.assert_called_once()


def test_test_connection_checks_imap_and_smtp() -> None:
    mock_imap = MagicMock()
    mock_smtp = MagicMock()
    with (
        patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_imap),
        patch("app.inbox.adapters.yahoo.smtplib.SMTP", return_value=mock_smtp),
    ):
        result = YahooMailbox().test_connection(CTX)

    assert result.imap_ok is True
    assert result.smtp_ok is True
    assert result.error is None
    mock_smtp.noop.assert_called_once()


def test_move_message_uses_uid_move_when_supported() -> None:
    mock_client = MagicMock()
    mock_client.capabilities = (b"IMAP4REV1", b"MOVE")
    mock_client.uid.return_value = ("OK", None)

    with patch("app.inbox.adapters.yahoo.imaplib.IMAP4_SSL", return_value=mock_client):
        result = YahooMailbox().move_message(CTX, uid=9, destination="HeadStart/General")

    assert result.status == "moved"
    mock_client.uid.assert_called_with("MOVE", "9", "HeadStart/General")
