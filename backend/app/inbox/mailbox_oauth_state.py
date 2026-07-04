"""Signed OAuth state with a per-flow nonce for CSRF protection."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.base import utcnow


@dataclass(frozen=True)
class IssuedMailboxOAuthState:
    """Signed provider state plus the httpOnly cookie nonce bound to the initiator."""

    state: str
    nonce: str


def issue_mailbox_oauth_state(*, user_id: int, state_type: str) -> IssuedMailboxOAuthState:
    """Issue a short-lived signed state token with a single-use browser nonce."""
    nonce = secrets.token_urlsafe(16)
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": state_type,
        "nonce": nonce,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return IssuedMailboxOAuthState(state=token, nonce=nonce)


def parse_mailbox_oauth_state(*, state: str, state_type: str, error_message: str) -> tuple[int, str]:
    """Validate OAuth state and return the owning user id and bound nonce."""
    try:
        payload: dict[str, Any] = jwt.decode(
            state, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise ValidationError(error_message) from exc
    if payload.get("type") != state_type:
        raise ValidationError(error_message)
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise ValidationError(error_message)
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise ValidationError(error_message)
    return int(sub), nonce


def verify_mailbox_oauth_nonce(cookie_nonce: str | None, expected_nonce: str) -> None:
    """Reject OAuth callbacks when the browser cookie does not match signed state."""
    if not cookie_nonce or not secrets.compare_digest(cookie_nonce, expected_nonce):
        raise ValidationError(
            "OAuth session mismatch. Start mailbox connect again from Settings."
        )
