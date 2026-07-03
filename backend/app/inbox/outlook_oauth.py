"""Microsoft identity OAuth helpers for the Outlook mailbox connector."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.inbox.types import OutlookMailboxConfig
from app.models.base import utcnow

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"
OUTLOOK_SCOPES = (
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
)
OUTLOOK_OAUTH_STATE_TYPE = "outlook_oauth"


class OutlookOAuthError(ValidationError):
    """Raised when Outlook OAuth is misconfigured or the flow fails."""


def outlook_oauth_configured() -> bool:
    """Return True when client id, secret, and redirect URI are all set."""
    return bool(
        settings.outlook_oauth_client_id
        and settings.outlook_oauth_client_secret
        and settings.outlook_oauth_redirect_uri
    )


def require_outlook_oauth_configured() -> None:
    """Raise when Outlook OAuth env vars are missing."""
    if not outlook_oauth_configured():
        raise OutlookOAuthError(
            "Outlook OAuth is not configured "
            "(set OUTLOOK_OAUTH_CLIENT_ID, OUTLOOK_OAUTH_CLIENT_SECRET, "
            "and OUTLOOK_OAUTH_REDIRECT_URI)."
        )


def create_outlook_oauth_state(user_id: int) -> str:
    """Issue a short-lived signed state token tying the callback to one user."""
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": OUTLOOK_OAUTH_STATE_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_outlook_oauth_state(state: str) -> int:
    """Validate OAuth state and return the owning user id."""
    try:
        payload: dict[str, Any] = jwt.decode(
            state, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise OutlookOAuthError("Invalid or expired Outlook OAuth state.") from exc
    if payload.get("type") != OUTLOOK_OAUTH_STATE_TYPE:
        raise OutlookOAuthError("Invalid Outlook OAuth state.")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise OutlookOAuthError("Invalid Outlook OAuth state.")
    return int(sub)


def build_outlook_authorization_url(*, state: str) -> str:
    """Return the Microsoft consent URL for Graph mail access."""
    require_outlook_oauth_configured()
    params = {
        "client_id": settings.outlook_oauth_client_id,
        "redirect_uri": settings.outlook_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(OUTLOOK_SCOPES),
        "response_mode": "query",
        "state": state,
    }
    return f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"


def exchange_outlook_code(code: str) -> OutlookMailboxConfig:
    """Exchange an authorization code for stored Outlook OAuth credentials."""
    require_outlook_oauth_configured()
    response = httpx.post(
        MICROSOFT_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.outlook_oauth_client_id,
            "client_secret": settings.outlook_oauth_client_secret,
            "redirect_uri": settings.outlook_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise OutlookOAuthError("Microsoft rejected the authorization code.")
    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise OutlookOAuthError("Microsoft token response did not include an access token.")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise OutlookOAuthError(
            "Microsoft did not return a refresh token. Revoke prior access and reconnect."
        )
    expires_in = token_data.get("expires_in")
    token_expiry = None
    if isinstance(expires_in, int) and expires_in > 0:
        token_expiry = (utcnow() + timedelta(seconds=expires_in)).isoformat()
    email_address = _fetch_outlook_profile_email(access_token)
    return OutlookMailboxConfig(
        email_address=email_address,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expiry=token_expiry,
    )


def refresh_outlook_access_token(config: OutlookMailboxConfig) -> OutlookMailboxConfig:
    """Refresh an expired Outlook access token using the stored refresh token."""
    require_outlook_oauth_configured()
    response = httpx.post(
        MICROSOFT_TOKEN_URL,
        data={
            "client_id": settings.outlook_oauth_client_id,
            "client_secret": settings.outlook_oauth_client_secret,
            "refresh_token": config.refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(OUTLOOK_SCOPES),
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise OutlookOAuthError("Failed to refresh Outlook access token.")
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OutlookOAuthError("Microsoft refresh response did not include an access token.")
    refresh_token = token_data.get("refresh_token")
    updates: dict[str, str] = {"access_token": access_token}
    if isinstance(refresh_token, str) and refresh_token:
        updates["refresh_token"] = refresh_token
    expires_in = token_data.get("expires_in")
    if isinstance(expires_in, int) and expires_in > 0:
        updates["token_expiry"] = (utcnow() + timedelta(seconds=expires_in)).isoformat()
    return config.model_copy(update=updates)


def outlook_token_needs_refresh(config: OutlookMailboxConfig) -> bool:
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


def _fetch_outlook_profile_email(access_token: str) -> str:
    response = httpx.get(
        GRAPH_ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"$select": "mail,userPrincipalName"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise OutlookOAuthError("Could not read the connected Outlook profile.")
    profile = response.json()
    email_address = profile.get("mail") or profile.get("userPrincipalName")
    if not isinstance(email_address, str) or not email_address:
        raise OutlookOAuthError("Outlook profile did not include an email address.")
    return email_address
