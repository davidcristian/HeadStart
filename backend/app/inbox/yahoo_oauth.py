"""Yahoo identity OAuth helpers for the Yahoo mailbox connector."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.inbox.mailbox_oauth_state import (
    IssuedMailboxOAuthState,
    code_challenge_s256,
    issue_mailbox_oauth_state,
    parse_mailbox_oauth_state,
)
from app.inbox.types import YahooMailboxConfig
from app.models.base import utcnow

YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_REVOKE_URL = "https://api.login.yahoo.com/oauth2/revoke"
YAHOO_USERINFO_URL = "https://api.login.yahoo.com/openid/v1/userinfo"
YAHOO_SCOPES = ("openid", "email", "mail-w")
YAHOO_OAUTH_STATE_TYPE = "yahoo_oauth"


class YahooOAuthError(ValidationError):
    """Raised when Yahoo OAuth is misconfigured or the flow fails."""


def yahoo_oauth_configured() -> bool:
    """Return True when client id, secret, and redirect URI are all set."""
    return bool(
        settings.yahoo_oauth_client_id
        and settings.yahoo_oauth_client_secret
        and settings.yahoo_oauth_redirect_uri
    )


def require_yahoo_oauth_configured() -> None:
    """Raise when Yahoo OAuth env vars are missing."""
    if not yahoo_oauth_configured():
        raise YahooOAuthError(
            "Yahoo OAuth is not configured "
            "(set YAHOO_OAUTH_CLIENT_ID, YAHOO_OAUTH_CLIENT_SECRET, "
            "and YAHOO_OAUTH_REDIRECT_URI)."
        )


def create_yahoo_oauth_state(user_id: int) -> IssuedMailboxOAuthState:
    """Issue a short-lived signed state token tying the callback to one user."""
    return issue_mailbox_oauth_state(user_id=user_id, state_type=YAHOO_OAUTH_STATE_TYPE)


def decode_yahoo_oauth_state(state: str) -> tuple[int, str, str]:
    """Validate OAuth state and return user id, nonce, and PKCE code_verifier."""
    try:
        return parse_mailbox_oauth_state(
            state=state,
            state_type=YAHOO_OAUTH_STATE_TYPE,
            error_message="Invalid or expired Yahoo OAuth state.",
        )
    except ValidationError as exc:
        raise YahooOAuthError(str(exc)) from exc


def build_yahoo_authorization_url(*, state: str, code_verifier: str) -> str:
    """Return the Yahoo consent URL for Mail API access (with PKCE S256)."""
    require_yahoo_oauth_configured()
    params = {
        "client_id": settings.yahoo_oauth_client_id,
        "redirect_uri": settings.yahoo_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(YAHOO_SCOPES),
        "state": state,
        "code_challenge": code_challenge_s256(code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{YAHOO_AUTH_URL}?{urlencode(params)}"


def exchange_yahoo_code(code: str, *, code_verifier: str) -> YahooMailboxConfig:
    """Exchange an authorization code for stored Yahoo OAuth credentials."""
    require_yahoo_oauth_configured()
    response = httpx.post(
        YAHOO_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.yahoo_oauth_client_id,
            "client_secret": settings.yahoo_oauth_client_secret,
            "redirect_uri": settings.yahoo_oauth_redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise YahooOAuthError("Yahoo rejected the authorization code.")
    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise YahooOAuthError("Yahoo token response did not include an access token.")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise YahooOAuthError(
            "Yahoo did not return a refresh token. Revoke prior access and reconnect."
        )
    expires_in = token_data.get("expires_in")
    token_expiry = None
    if isinstance(expires_in, int) and expires_in > 0:
        token_expiry = (utcnow() + timedelta(seconds=expires_in)).isoformat()
    email_address = _fetch_yahoo_profile_email(access_token)
    return YahooMailboxConfig(
        email_address=email_address,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=token_expiry,
    )


def refresh_yahoo_access_token(config: YahooMailboxConfig) -> YahooMailboxConfig:
    """Refresh an expired Yahoo access token using the stored refresh token."""
    require_yahoo_oauth_configured()
    response = httpx.post(
        YAHOO_TOKEN_URL,
        data={
            "client_id": settings.yahoo_oauth_client_id,
            "client_secret": settings.yahoo_oauth_client_secret,
            "refresh_token": config.refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise YahooOAuthError("Failed to refresh Yahoo access token.")
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise YahooOAuthError("Yahoo refresh response did not include an access token.")
    refresh_token = token_data.get("refresh_token")
    updates: dict[str, str] = {"access_token": access_token}
    if isinstance(refresh_token, str) and refresh_token:
        updates["refresh_token"] = refresh_token
    expires_in = token_data.get("expires_in")
    if isinstance(expires_in, int) and expires_in > 0:
        updates["token_expiry"] = (utcnow() + timedelta(seconds=expires_in)).isoformat()
    return config.model_copy(update=updates)


def yahoo_token_needs_refresh(config: YahooMailboxConfig) -> bool:
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


def revoke_yahoo_tokens(config: YahooMailboxConfig) -> None:
    """Revoke the stored Yahoo refresh token at Yahoo."""
    require_yahoo_oauth_configured()
    response = httpx.post(
        YAHOO_REVOKE_URL,
        data={"token": config.refresh_token},
        auth=(settings.yahoo_oauth_client_id, settings.yahoo_oauth_client_secret),
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise YahooOAuthError(f"Yahoo token revoke failed with HTTP {response.status_code}.")


def _fetch_yahoo_profile_email(access_token: str) -> str:
    response = httpx.get(
        YAHOO_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise YahooOAuthError("Could not read the connected Yahoo profile.")
    email_address = response.json().get("email")
    if not isinstance(email_address, str) or not email_address:
        raise YahooOAuthError("Yahoo profile did not include an email address.")
    return email_address
