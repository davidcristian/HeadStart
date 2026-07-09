"""Registration helpers for AuthService (keeps auth.py under the LOC cap)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.auth_events import log_auth_event
from app.core.email import send_existing_account_email
from app.core.exceptions import RateLimitError
from app.core.rate_limit import FORGOT_EMAIL, enforce_rate_limit
from app.core.security import hash_password
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest

# Same body for create and duplicate so /register cannot enumerate emails (AUT-27).
REGISTER_ACK_MESSAGE = (
    "If this email is available, we created an account and sent a verification link. "
    "Check your inbox."
)


def register_account(
    session: Session,
    data: RegisterRequest,
    *,
    ip_address: str | None = None,
    issue_verification: Callable[[User], None],
) -> User | None:
    """Create an account when the email is free; never reveal whether it was taken.

    Returns the new user on create, or ``None`` when the email already exists.
    HTTP callers must always return :data:`REGISTER_ACK_MESSAGE`.
    """
    email = data.email.lower()
    users = UserRepository(session)
    # Burn bcrypt on both paths so existence is not obvious from CPU time.
    password_hash = hash_password(data.password)
    existing = users.get_by_email(email)
    if existing is not None:
        _acknowledge_existing_registration(
            existing,
            email=email,
            ip_address=ip_address,
        )
        return None

    user = User(
        email=email,
        password_hash=password_hash,
        is_admin=False,
        is_active=True,
    )
    user = users.add(user)
    if users.claim_bootstrap_admin(user.id):
        user.is_admin = True
        session.flush()
    issue_verification(user)
    log_auth_event(
        "register_created",
        email=user.email,
        user_id=user.id,
        ip_address=ip_address,
        issued=True,
    )
    return user


def _acknowledge_existing_registration(
    user: User,
    *,
    email: str,
    ip_address: str | None,
) -> None:
    """Notify an existing account without changing the HTTP response (AUT-27)."""
    if not user.is_active:
        log_auth_event(
            "register_duplicate",
            email=email,
            user_id=user.id,
            ip_address=ip_address,
            issued=False,
            reason="inactive",
        )
        return
    # Cap outbound notices per address (same ceiling as forgot-password mail).
    # Swallow RateLimitError so a 429 cannot re-enumerate existing addresses.
    try:
        enforce_rate_limit(f"auth:register:email_issue:{email}", FORGOT_EMAIL)
    except RateLimitError:
        log_auth_event(
            "register_duplicate",
            email=user.email,
            user_id=user.id,
            ip_address=ip_address,
            issued=False,
            reason="rate_limited",
        )
        return
    send_existing_account_email(to_email=user.email)
    log_auth_event(
        "register_duplicate",
        email=user.email,
        user_id=user.id,
        ip_address=ip_address,
        issued=True,
    )
