"""Branch coverage for mailbox email resolution (imap_smtp wrong config type)."""

import pytest

from app.inbox.mailbox_email import mailbox_email_from_context
from app.inbox.types import GmailMailboxConfig, MailboxContext


def test_imap_smtp_context_rejects_oauth_config() -> None:
    ctx = MailboxContext(
        connector_type="imap_smtp",
        config=GmailMailboxConfig(
            email_address="user@gmail.com", access_token="a", refresh_token="r"
        ),
    )
    with pytest.raises(TypeError, match="imap_smtp connector requires MailboxConfig"):
        mailbox_email_from_context(ctx)
