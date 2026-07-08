"""Google OAuth helpers for the Gmail mailbox connector."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.inbox.mailbox_oauth_state import (
    IssuedMailboxOAuthState,
    issue_mailbox_oauth_state,
    parse_mailbox_oauth_state,
)
from app.inbox.types import GmailMailboxConfig
from app.models.base import utcnow

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
)
GMAIL_OAUTH_STATE_TYPE = "gmail_oauth"


class GmailOAuthError(ValidationError):
    """Raised when Gmail OAuth is misconfigured or the flow fails."""


def gmail_oauth_configured() -> bool:
    """Return True when client id, secret, and redirect URI are all set."""
    return bool(
        settings.gmail_oauth_client_id
        and settings.gmail_oauth_client_secret
        and settings.gmail_oauth_redirect_uri
    )


def require_gmail_oauth_configured() -> None:
    """Raise when Gmail OAuth env vars are missing."""
    if not gmail_oauth_configured():
        raise GmailOAuthError(
            "Gmail OAuth is not configured "
            "(set GMAIL_OAUTH_CLIENT_ID, GMAIL_OAUTH_CLIENT_SECRET, "
            "and GMAIL_OAUTH_REDIRECT_URI)."
        )


def create_gmail_oauth_state(user_id: int) -> IssuedMailboxOAuthState:
    """Issue a short-lived signed state token tying the callback to one user."""
    return issue_mailbox_oauth_state(user_id=user_id, state_type=GMAIL_OAUTH_STATE_TYPE)


def decode_gmail_oauth_state(state: str) -> tuple[int, str]:
    """Validate OAuth state and return the owning user id and bound nonce."""
    try:
        return parse_mailbox_oauth_state(
            state=state,
            state_type=GMAIL_OAUTH_STATE_TYPE,
            error_message="Invalid or expired Gmail OAuth state.",
        )
    except ValidationError as exc:
        raise GmailOAuthError(str(exc)) from exc


def build_gmail_authorization_url(*, state: str) -> str:
    """Return the Google consent URL for Gmail API access."""
    require_gmail_oauth_configured()
    params = {
        "client_id": settings.gmail_oauth_client_id,
        "redirect_uri": settings.gmail_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_gmail_code(code: str) -> GmailMailboxConfig:
    """Exchange an authorization code for stored Gmail OAuth credentials."""
    require_gmail_oauth_configured()
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.gmail_oauth_client_id,
            "client_secret": settings.gmail_oauth_client_secret,
            "redirect_uri": settings.gmail_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise GmailOAuthError("Google rejected the authorization code.")
    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailOAuthError("Google token response did not include an access token.")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise GmailOAuthError(
            "Google did not return a refresh token. Revoke prior access and reconnect "
            "with prompt=consent."
        )
    expires_in = token_data.get("expires_in")
    token_expiry = None
    if isinstance(expires_in, int) and expires_in > 0:
        token_expiry = (utcnow() + timedelta(seconds=expires_in)).isoformat()
    email_address = _fetch_gmail_profile_email(access_token)
    return GmailMailboxConfig(
        email_address=email_address,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=token_expiry,
    )


def refresh_gmail_access_token(config: GmailMailboxConfig) -> GmailMailboxConfig:
    """Refresh an expired Gmail access token using the stored refresh token."""
    require_gmail_oauth_configured()
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.gmail_oauth_client_id,
            "client_secret": settings.gmail_oauth_client_secret,
            "refresh_token": config.refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise GmailOAuthError("Failed to refresh Gmail access token.")
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailOAuthError("Google refresh response did not include an access token.")
    expires_in = token_data.get("expires_in")
    token_expiry = config.token_expiry
    if isinstance(expires_in, int) and expires_in > 0:
        token_expiry = (utcnow() + timedelta(seconds=expires_in)).isoformat()
    return config.model_copy(update={"access_token": access_token, "token_expiry": token_expiry})


def gmail_token_needs_refresh(config: GmailMailboxConfig) -> bool:
    """Return True when the access token is missing or near expiry."""
    if not config.access_token:
        return True
    if not config.token_expiry:
        return False
    try:
        from datetime import datetime

        expiry = datetime.fromisoformat(config.token_expiry)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=utcnow().tzinfo)
    except ValueError:
        return True
    return expiry <= utcnow() + timedelta(minutes=2)


def revoke_gmail_tokens(config: GmailMailboxConfig) -> None:
    """Revoke the stored Gmail refresh token at Google."""
    require_gmail_oauth_configured()
    response = httpx.post(
        GOOGLE_REVOKE_URL,
        data={"token": config.refresh_token},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise GmailOAuthError(f"Google token revoke failed with HTTP {response.status_code}.")


def _fetch_gmail_profile_email(access_token: str) -> str:
    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise GmailOAuthError("Could not read the connected Gmail profile.")
    email_address = response.json().get("emailAddress")
    if not isinstance(email_address, str) or not email_address:
        raise GmailOAuthError("Gmail profile did not include an email address.")
    return email_address
