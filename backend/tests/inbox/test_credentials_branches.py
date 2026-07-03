"""Branch coverage for mailbox credential helpers (imap read + all exports)."""

from datetime import UTC, datetime

from app.core.config import settings
from app.inbox.credentials import (
    encode_mailbox_config,
    env_mailbox_config,
    mailbox_config_for_export,
    mailbox_credential_to_read,
)
from app.inbox.types import (
    FastmailMailboxConfig,
    MailboxConfig,
    OutlookMailboxConfig,
    YahooMailboxConfig,
)
from app.models.mailbox_credential import MailboxCredential


def _credential(*, connector_type, config) -> MailboxCredential:
    return MailboxCredential(
        id=1,
        user_id=42,
        connector_type=connector_type,
        secret_ciphertext=encode_mailbox_config(config),
        enabled=True,
        created_at=datetime(2026, 6, 30, tzinfo=UTC),
    )


def test_mailbox_credential_to_read_maps_imap_hosts() -> None:
    credential = _credential(
        connector_type="imap_smtp",
        config=MailboxConfig(
            imap_host="imap.example.com",
            imap_user="login@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com",
        ),
    )
    read = mailbox_credential_to_read(credential)
    assert read.imap_host == "imap.example.com"
    assert read.smtp_host == "smtp.example.com"
    assert read.imap_user == "login@example.com"
    assert read.email_address is None


def test_export_covers_outlook_yahoo_fastmail() -> None:
    outlook = _credential(
        connector_type="outlook",
        config=OutlookMailboxConfig(
            email_address="u@outlook.com", access_token="a", refresh_token="r"
        ),
    )
    outlook_export = mailbox_config_for_export(outlook)
    assert outlook_export["connector_type"] == "outlook"
    assert outlook_export["access_token"] == "[redacted]"
    assert outlook_export["refresh_token"] == "[redacted]"

    yahoo = _credential(
        connector_type="yahoo",
        config=YahooMailboxConfig(email_address="u@yahoo.com", access_token="a", refresh_token="r"),
    )
    yahoo_export = mailbox_config_for_export(yahoo)
    assert yahoo_export["connector_type"] == "yahoo"
    assert yahoo_export["refresh_token"] == "[redacted]"

    fastmail = _credential(
        connector_type="fastmail",
        config=FastmailMailboxConfig(email_address="u@fastmail.com", api_token="token"),
    )
    fastmail_export = mailbox_config_for_export(fastmail)
    assert fastmail_export["connector_type"] == "fastmail"
    assert fastmail_export["api_token"] == "[redacted]"


def test_env_mailbox_config_returns_none_when_incomplete(monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    monkeypatch.setattr(settings, "inbox_imap_host", "imap.example.com")
    monkeypatch.setattr(settings, "inbox_imap_user", "")
    monkeypatch.setattr(settings, "inbox_imap_password", "secret")
    monkeypatch.setattr(settings, "inbox_smtp_host", "smtp.example.com")
    assert env_mailbox_config() is None
