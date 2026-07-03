"""Tests for resolving mailbox email addresses from connector context."""

import pytest

from app.inbox.mailbox_email import mailbox_email_from_context, mailbox_email_from_read
from app.inbox.types import GmailMailboxConfig, MailboxConfig, MailboxContext


def test_mailbox_email_from_context_uses_oauth_address() -> None:
    ctx = MailboxContext(
        connector_type="gmail",
        config=GmailMailboxConfig(
            email_address="user@gmail.com",
            access_token="access",
            refresh_token="refresh",
        ),
    )
    assert mailbox_email_from_context(ctx) == "user@gmail.com"


def test_mailbox_email_from_context_prefers_smtp_from_for_imap() -> None:
    ctx = MailboxContext(
        connector_type="imap_smtp",
        config=MailboxConfig(
            imap_host="imap.example.com",
            imap_user="login@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com",
            smtp_from="display@example.com",
        ),
    )
    assert mailbox_email_from_context(ctx) == "display@example.com"


def test_mailbox_email_from_read_maps_connector_types() -> None:
    assert (
        mailbox_email_from_read(
            connector_type="outlook",
            imap_user=None,
            email_address="user@outlook.com",
        )
        == "user@outlook.com"
    )
    assert (
        mailbox_email_from_read(
            connector_type="imap_smtp",
            imap_user="user@example.com",
            email_address=None,
        )
        == "user@example.com"
    )


def test_mailbox_email_from_context_rejects_wrong_config_type() -> None:
    ctx = MailboxContext(
        connector_type="yahoo",
        config=MailboxConfig(
            imap_host="imap.example.com",
            imap_user="user@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com",
        ),
    )
    with pytest.raises(TypeError, match="yahoo connector requires"):
        mailbox_email_from_context(ctx)
