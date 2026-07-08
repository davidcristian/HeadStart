"""Structured auth security event logging for operators (AUT-10)."""

from __future__ import annotations

from typing import Any, Literal

from app.core.logging import get_logger
from app.core.metrics import record_auth_login_failure
from app.core.security import pseudonymize_email_for_audit

logger = get_logger(__name__)

AuthEvent = Literal[
    "login_success",
    "login_failure",
    "password_reset_requested",
    "password_reset_completed",
    "session_invalidated",
    "account_deleted",
]


def log_auth_event(
    event: AuthEvent,
    *,
    email: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
    reason: str | None = None,
    issued: bool | None = None,
) -> None:
    """Emit one auth security log line; never includes plaintext email or tokens."""
    parts = [f"auth_event={event}"]
    extra: dict[str, Any] = {"auth_event": event}
    if email is not None:
        email_hash = pseudonymize_email_for_audit(email)
        parts.append(f"email_hash={email_hash}")
        extra["email_hash"] = email_hash
    if user_id is not None:
        parts.append(f"user_id={user_id}")
        extra["user_id"] = user_id
    if ip_address is not None:
        parts.append(f"ip={ip_address}")
        extra["ip"] = ip_address
    if reason is not None:
        parts.append(f"reason={reason}")
        extra["reason"] = reason
    if issued is not None:
        parts.append(f"issued={str(issued).lower()}")
        extra["issued"] = issued
    logger.info(" ".join(parts), extra=extra)
    if event == "login_failure":
        record_auth_login_failure()
