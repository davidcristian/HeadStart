"""Tests for mailbox credential encode/decode helpers."""

from datetime import UTC, datetime

from app.core.config import settings
from app.inbox.credentials import (
    decode_mailbox_config,
    encode_mailbox_config,
    env_mailbox_config,
    mailbox_config_for_export,
    mailbox_credential_to_read,
)
from app.inbox.types import (
    FastmailMailboxConfig,
    GmailMailboxConfig,
    MailboxConfig,
    OutlookMailboxConfig,
    YahooMailboxConfig,
)
from app.models.mailbox_credential import MailboxCredential


def _credential(
    *,
    connector_type: str,
    config: (
        MailboxConfig
        | GmailMailboxConfig
        | OutlookMailboxConfig
        | YahooMailboxConfig
        | FastmailMailboxConfig
    ),
) -> MailboxCredential:
    return MailboxCredential(
        id=1,
        user_id=42,
        connector_type=connector_type,
        secret_ciphertext=encode_mailbox_config(config),
        enabled=True,
        created_at=datetime(2026, 6, 30, tzinfo=UTC),
    )


def test_encode_decode_imap_smtp_round_trip() -> None:
    config = MailboxConfig(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="imap-secret",
        smtp_host="smtp.example.com",
        smtp_password="smtp-secret",
        smtp_from="user@example.com",
    )
    credential = _credential(connector_type="imap_smtp", config=config)
    decoded = decode_mailbox_config(credential)
    assert isinstance(decoded, MailboxConfig)
    assert decoded.imap_host == "imap.example.com"
    assert decoded.imap_password == "imap-secret"
    assert decoded.smtp_password == "smtp-secret"


def test_encode_decode_oauth_connectors_round_trip() -> None:
    cases = (
        (
            "gmail",
            GmailMailboxConfig(
                email_address="u@gmail.com",
                access_token="a",
                refresh_token="r",
            ),
        ),
        (
            "outlook",
            OutlookMailboxConfig(
                email_address="u@outlook.com",
                access_token="a",
                refresh_token="r",
            ),
        ),
        (
            "yahoo",
            YahooMailboxConfig(
                email_address="u@yahoo.com",
                access_token="a",
                refresh_token="r",
            ),
        ),
        (
            "fastmail",
            FastmailMailboxConfig(email_address="u@fastmail.com", api_token="token"),
        ),
    )
    for connector_type, config in cases:
        credential = _credential(connector_type=connector_type, config=config)
        decoded = decode_mailbox_config(credential)
        assert decoded.email_address == config.email_address
        if isinstance(config, FastmailMailboxConfig):
            assert decoded.api_token == "token"
        else:
            assert decoded.access_token == "a"
            assert decoded.refresh_token == "r"


def test_mailbox_credential_to_read_maps_oauth_email() -> None:
    credential = _credential(
        connector_type="gmail",
        config=GmailMailboxConfig(
            email_address="user@gmail.com",
            access_token="access",
            refresh_token="refresh",
        ),
    )
    read = mailbox_credential_to_read(credential)
    assert read.email_address == "user@gmail.com"
    assert read.imap_host is None
    assert read.has_config is True


def test_mailbox_config_for_export_redacts_secrets() -> None:
    imap = _credential(
        connector_type="imap_smtp",
        config=MailboxConfig(
            imap_host="imap.example.com",
            imap_user="user@example.com",
            imap_password="imap-secret",
            smtp_host="smtp.example.com",
            smtp_password="smtp-secret",
        ),
    )
    exported = mailbox_config_for_export(imap)
    assert exported["imap_password"] == "[redacted]"
    assert exported["smtp_password"] == "[redacted]"
    assert exported["imap_user"] == "user@example.com"

    gmail = _credential(
        connector_type="gmail",
        config=GmailMailboxConfig(
            email_address="user@gmail.com",
            access_token="access",
            refresh_token="refresh",
        ),
    )
    oauth_export = mailbox_config_for_export(gmail)
    assert oauth_export["access_token"] == "[redacted]"
    assert oauth_export["refresh_token"] == "[redacted]"


def test_env_mailbox_config_returns_none_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_use_env_credentials", False)
    monkeypatch.setattr(settings, "inbox_imap_host", "imap.example.com")
    assert env_mailbox_config() is None


def test_env_mailbox_config_builds_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    monkeypatch.setattr(settings, "inbox_imap_host", "imap.example.com")
    monkeypatch.setattr(settings, "inbox_imap_user", "user@example.com")
    monkeypatch.setattr(settings, "inbox_imap_password", "imap-secret")
    monkeypatch.setattr(settings, "inbox_smtp_host", "smtp.example.com")
    config = env_mailbox_config()
    assert config is not None
    assert config.imap_user == "user@example.com"
    assert config.smtp_host == "smtp.example.com"
