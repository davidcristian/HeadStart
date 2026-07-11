"""Resolve the user's mailbox email address from a connector context."""

from app.inbox.ghost_message import mailbox_self_address
from app.inbox.types import (
    OAUTH_CONFIG_TYPES,
    OAUTH_CONNECTOR_TYPES,
    MailboxConfig,
    MailboxContext,
)


def mailbox_email_from_context(ctx: MailboxContext) -> str:
    """Return the address used for self-ghost detection and outbound From headers."""
    if ctx.connector_type in OAUTH_CONNECTOR_TYPES:
        config = ctx.config
        if not isinstance(config, OAUTH_CONFIG_TYPES):
            raise TypeError(f"{ctx.connector_type} connector requires OAuth/API mailbox config")
        return config.email_address
    if not isinstance(ctx.config, MailboxConfig):
        raise TypeError("imap_smtp connector requires MailboxConfig")
    return mailbox_self_address(
        imap_user=ctx.config.imap_user,
        smtp_from=ctx.config.smtp_from,
    )


def mailbox_email_from_read(
    *,
    connector_type: str,
    imap_user: str | None,
    email_address: str | None,
) -> str:
    """Return the mailbox email from a credential read DTO."""
    if connector_type in OAUTH_CONNECTOR_TYPES:
        return email_address or ""
    return imap_user or ""
