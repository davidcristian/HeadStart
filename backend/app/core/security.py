"""Password hashing (bcrypt) and JWT issuing/verification (PyJWT).

This module is framework-agnostic: it knows nothing about FastAPI. The auth
dependency that turns a request into a `User` lives in `app.api.deps`.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings
from app.models.base import utcnow

# bcrypt only hashes the first 72 bytes; longer inputs raise in newer releases.
_BCRYPT_MAX_BYTES = 72

TokenType = Literal["access", "refresh", "feed"]


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or the wrong type."""


def _truncate(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage."""
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        return bcrypt.checkpw(_truncate(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def generate_password_reset_token() -> str:
    """Return a URL-safe random token for password reset links."""
    return secrets.token_urlsafe(32)


def create_feed_token(subject: str | int, *, version: int) -> str:
    """Issue a long-lived JWT for unauthenticated RSS feed access."""
    now = utcnow()
    payload = {
        "sub": str(subject),
        "type": "feed",
        "ver": version,
        "iat": now,
        "exp": now + timedelta(days=3650),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_feed_token(token: str) -> dict[str, Any]:
    """Decode and validate a feed JWT. Raises `TokenError`."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "ver"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != "feed":
        raise TokenError("Expected a feed token.")
    return payload


def hash_password_reset_token(token: str) -> str:
    """One-way hash of a reset token for storage (not bcrypt — token is already random)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def pseudonymize_email_for_audit(email: str) -> str:
    """One-way account reference for GDPR audit rows that outlive the user."""
    digest = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        email.strip().lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"erased:{digest}"


def _create_token(subject: str, token_type: TokenType, expires: timedelta, version: int) -> str:
    now = utcnow()
    payload = {
        "sub": subject,
        "type": token_type,
        "ver": version,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str | int, *, version: int) -> str:
    return _create_token(
        str(subject), "access", timedelta(minutes=settings.access_token_expire_minutes), version
    )


def create_refresh_token(subject: str | int, *, version: int) -> str:
    return _create_token(
        str(subject), "refresh", timedelta(days=settings.refresh_token_expire_days), version
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing its `type`. Raises `TokenError`."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "ver"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token.")
    return payload
