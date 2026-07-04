"""httpOnly cookies binding mailbox OAuth callbacks to the initiating browser."""

from __future__ import annotations

from fastapi import Response

from app.core.config import settings

MAILBOX_OAUTH_COOKIE_NAME = "headstart_mailbox_oauth_nonce"
MAILBOX_OAUTH_COOKIE_PATH = "/api/v1/inbox"
MAILBOX_OAUTH_COOKIE_MAX_AGE = 15 * 60


def set_mailbox_oauth_nonce_cookie(response: Response, nonce: str) -> None:
    """Store the OAuth nonce in an httpOnly cookie scoped to inbox routes."""
    response.set_cookie(
        key=MAILBOX_OAUTH_COOKIE_NAME,
        value=nonce,
        max_age=MAILBOX_OAUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
        path=MAILBOX_OAUTH_COOKIE_PATH,
    )


def clear_mailbox_oauth_nonce_cookie(response: Response) -> None:
    """Remove the OAuth nonce cookie after callback handling."""
    response.delete_cookie(
        key=MAILBOX_OAUTH_COOKIE_NAME,
        path=MAILBOX_OAUTH_COOKIE_PATH,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
    )
