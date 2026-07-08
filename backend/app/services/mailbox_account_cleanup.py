"""Best-effort mailbox OAuth teardown when a local account is deleted."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.inbox.credentials import decode_mailbox_config
from app.inbox.gmail_oauth import revoke_gmail_tokens
from app.inbox.types import GmailMailboxConfig, OutlookMailboxConfig, YahooMailboxConfig
from app.inbox.yahoo_oauth import revoke_yahoo_tokens
from app.repositories.mailbox_credentials import MailboxCredentialRepository

logger = logging.getLogger(__name__)


def release_mailbox_oauth(session: Session, user_id: int) -> None:
    """Revoke provider OAuth grants for the user's mailbox before local delete.

    Provider failures are logged and swallowed so GDPR deletion still completes
    when Google/Yahoo are unreachable or the grant is already gone. Outlook has
    no safe per-app revoke API with Mail.* scopes; those tokens are discarded
    locally only (user can revoke at account.microsoft.com). IMAP/Fastmail have
    no OAuth refresh grant to revoke.
    """
    credential = MailboxCredentialRepository(session).get_for_user(user_id)
    if credential is None:
        return
    try:
        config = decode_mailbox_config(credential)
    except Exception as exc:
        logger.warning(
            "mailbox OAuth decode failed for deleted user %s: %s",
            user_id,
            exc,
        )
        return
    if isinstance(config, GmailMailboxConfig):
        _revoke_gmail(config, user_id=user_id)
    elif isinstance(config, YahooMailboxConfig):
        _revoke_yahoo(config, user_id=user_id)
    elif isinstance(config, OutlookMailboxConfig):
        logger.info(
            "Outlook mailbox OAuth for deleted user %s: no per-app Microsoft "
            "revoke API with Mail.* scopes; discarding tokens locally",
            user_id,
        )


def _revoke_gmail(config: GmailMailboxConfig, *, user_id: int) -> None:
    try:
        revoke_gmail_tokens(config)
        logger.info("revoked Gmail OAuth grant for deleted user %s", user_id)
    except Exception as exc:
        logger.warning(
            "Gmail OAuth revoke failed for deleted user %s: %s",
            user_id,
            exc,
        )


def _revoke_yahoo(config: YahooMailboxConfig, *, user_id: int) -> None:
    try:
        revoke_yahoo_tokens(config)
        logger.info("revoked Yahoo OAuth grant for deleted user %s", user_id)
    except Exception as exc:
        logger.warning(
            "Yahoo OAuth revoke failed for deleted user %s: %s",
            user_id,
            exc,
        )
