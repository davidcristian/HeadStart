"""OAuth authorize/callback helpers for inbox mailbox connectors."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.inbox.gmail_oauth import (
    build_gmail_authorization_url,
    create_gmail_oauth_state,
    decode_gmail_oauth_state,
    exchange_gmail_code,
    gmail_oauth_configured,
    require_gmail_oauth_configured,
)
from app.inbox.mailbox_oauth_state import verify_mailbox_oauth_nonce
from app.inbox.outlook_oauth import (
    build_outlook_authorization_url,
    create_outlook_oauth_state,
    decode_outlook_oauth_state,
    exchange_outlook_code,
    outlook_oauth_configured,
    require_outlook_oauth_configured,
)
from app.inbox.yahoo_oauth import (
    build_yahoo_authorization_url,
    create_yahoo_oauth_state,
    decode_yahoo_oauth_state,
    exchange_yahoo_code,
    require_yahoo_oauth_configured,
    yahoo_oauth_configured,
)
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.schemas.mailbox import (
    GmailAuthorizeResponse,
    GmailOAuthCallbackResult,
    OutlookAuthorizeResponse,
    YahooAuthorizeResponse,
)
from app.services.inbox_oauth import persist_oauth_mailbox


def gmail_authorize_url(user_id: int) -> tuple[GmailAuthorizeResponse, str]:
    """Return a Google OAuth consent URL and the browser-bound nonce."""
    require_gmail_oauth_configured()
    issued = create_gmail_oauth_state(user_id)
    return (
        GmailAuthorizeResponse(authorization_url=build_gmail_authorization_url(state=issued.state)),
        issued.nonce,
    )


def complete_gmail_oauth(
    session: Session,
    repo: MailboxCredentialRepository,
    *,
    code: str,
    state: str,
    oauth_nonce: str | None,
) -> GmailOAuthCallbackResult:
    """Exchange an OAuth callback for encrypted Gmail credentials."""
    user_id, expected_nonce = decode_gmail_oauth_state(state)
    verify_mailbox_oauth_nonce(oauth_nonce, expected_nonce)
    config = exchange_gmail_code(code)
    return persist_oauth_mailbox(
        session,
        repo,
        user_id=user_id,
        connector_type="gmail",
        config=config,
    )


def outlook_authorize_url(user_id: int) -> tuple[OutlookAuthorizeResponse, str]:
    """Return a Microsoft OAuth consent URL and the browser-bound nonce."""
    require_outlook_oauth_configured()
    issued = create_outlook_oauth_state(user_id)
    return (
        OutlookAuthorizeResponse(
            authorization_url=build_outlook_authorization_url(state=issued.state)
        ),
        issued.nonce,
    )


def complete_outlook_oauth(
    session: Session,
    repo: MailboxCredentialRepository,
    *,
    code: str,
    state: str,
    oauth_nonce: str | None,
) -> GmailOAuthCallbackResult:
    """Exchange an OAuth callback for encrypted Outlook credentials."""
    user_id, expected_nonce = decode_outlook_oauth_state(state)
    verify_mailbox_oauth_nonce(oauth_nonce, expected_nonce)
    config = exchange_outlook_code(code)
    return persist_oauth_mailbox(
        session,
        repo,
        user_id=user_id,
        connector_type="outlook",
        config=config,
    )


def yahoo_authorize_url(user_id: int) -> tuple[YahooAuthorizeResponse, str]:
    """Return a Yahoo OAuth consent URL and the browser-bound nonce."""
    require_yahoo_oauth_configured()
    issued = create_yahoo_oauth_state(user_id)
    return (
        YahooAuthorizeResponse(authorization_url=build_yahoo_authorization_url(state=issued.state)),
        issued.nonce,
    )


def complete_yahoo_oauth(
    session: Session,
    repo: MailboxCredentialRepository,
    *,
    code: str,
    state: str,
    oauth_nonce: str | None,
) -> GmailOAuthCallbackResult:
    """Exchange an OAuth callback for encrypted Yahoo credentials."""
    user_id, expected_nonce = decode_yahoo_oauth_state(state)
    verify_mailbox_oauth_nonce(oauth_nonce, expected_nonce)
    config = exchange_yahoo_code(code)
    return persist_oauth_mailbox(
        session,
        repo,
        user_id=user_id,
        connector_type="yahoo",
        config=config,
    )


def gmail_oauth_available() -> bool:
    """Whether the deployment exposes Gmail OAuth connect."""
    return gmail_oauth_configured()


def outlook_oauth_available() -> bool:
    """Whether the deployment exposes Outlook OAuth connect."""
    return outlook_oauth_configured()


def yahoo_oauth_available() -> bool:
    """Whether the deployment exposes Yahoo OAuth connect."""
    return yahoo_oauth_configured()
