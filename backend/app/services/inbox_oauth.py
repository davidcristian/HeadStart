"""OAuth mailbox credential persistence and token refresh for inbox connectors."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.inbox.credentials import decode_mailbox_config, encode_mailbox_config
from app.inbox.gmail_oauth import gmail_token_needs_refresh, refresh_gmail_access_token
from app.inbox.outlook_oauth import outlook_token_needs_refresh, refresh_outlook_access_token
from app.inbox.types import GmailMailboxConfig, OutlookMailboxConfig, YahooMailboxConfig
from app.inbox.yahoo_oauth import refresh_yahoo_access_token, yahoo_token_needs_refresh
from app.models.mailbox_credential import MailboxCredential
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.schemas.mailbox import GmailOAuthCallbackResult

OAuthConfig = GmailMailboxConfig | OutlookMailboxConfig | YahooMailboxConfig


def persist_oauth_mailbox(
    session: Session,
    repo: MailboxCredentialRepository,
    *,
    user_id: int,
    connector_type: str,
    config: OAuthConfig,
) -> GmailOAuthCallbackResult:
    """Store encrypted OAuth tokens for one mailbox connector."""
    credential = repo.get_for_user(user_id)
    ciphertext = encode_mailbox_config(config)
    if credential is None:
        credential = MailboxCredential(
            user_id=user_id,
            connector_type=connector_type,
            enabled=True,
            secret_ciphertext=ciphertext,
        )
        repo.add(credential)
    else:
        credential.connector_type = connector_type
        credential.enabled = True
        credential.secret_ciphertext = ciphertext
        session.flush()
    return GmailOAuthCallbackResult(
        connector_type=connector_type,
        email_address=config.email_address,
    )


def _ensure_fresh_oauth_config[
    TConfig: (
        GmailMailboxConfig,
        OutlookMailboxConfig,
        YahooMailboxConfig,
    )
](
    session: Session,
    credential: MailboxCredential,
    config: TConfig,
    *,
    config_type: type[TConfig],
    needs_refresh: Callable[[TConfig], bool],
    refresh: Callable[[TConfig], TConfig],
) -> TConfig:
    """Refresh under a row lock so concurrent ticks cannot rotate the same token."""
    if not needs_refresh(config):
        return config
    locked = MailboxCredentialRepository(session).get_for_user_for_update(credential.user_id)
    if locked is None:
        refreshed = refresh(config)
        credential.secret_ciphertext = encode_mailbox_config(refreshed)
        session.flush()
        return refreshed
    current = decode_mailbox_config(locked)
    if not isinstance(current, config_type):
        return config
    if not needs_refresh(current):
        # Another worker already refreshed while we waited for the lock.
        credential.secret_ciphertext = locked.secret_ciphertext
        return current
    refreshed = refresh(current)
    locked.secret_ciphertext = encode_mailbox_config(refreshed)
    credential.secret_ciphertext = locked.secret_ciphertext
    session.flush()
    return refreshed


def ensure_fresh_gmail_config(
    session: Session,
    credential: MailboxCredential,
    config: GmailMailboxConfig,
) -> GmailMailboxConfig:
    """Refresh and persist Gmail OAuth tokens when they are near expiry."""
    return _ensure_fresh_oauth_config(
        session,
        credential,
        config,
        config_type=GmailMailboxConfig,
        needs_refresh=gmail_token_needs_refresh,
        refresh=refresh_gmail_access_token,
    )


def ensure_fresh_outlook_config(
    session: Session,
    credential: MailboxCredential,
    config: OutlookMailboxConfig,
) -> OutlookMailboxConfig:
    """Refresh and persist Outlook OAuth tokens when they are near expiry."""
    return _ensure_fresh_oauth_config(
        session,
        credential,
        config,
        config_type=OutlookMailboxConfig,
        needs_refresh=outlook_token_needs_refresh,
        refresh=refresh_outlook_access_token,
    )


def ensure_fresh_yahoo_config(
    session: Session,
    credential: MailboxCredential,
    config: YahooMailboxConfig,
) -> YahooMailboxConfig:
    """Refresh and persist Yahoo OAuth tokens when they are near expiry."""
    return _ensure_fresh_oauth_config(
        session,
        credential,
        config,
        config_type=YahooMailboxConfig,
        needs_refresh=yahoo_token_needs_refresh,
        refresh=refresh_yahoo_access_token,
    )
