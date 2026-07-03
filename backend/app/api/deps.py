"""FastAPI dependencies."""

from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import SessionFactory
from app.core.security import TokenError, decode_token
from app.models.user import User
from app.repositories.users import UserRepository

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Missing or invalid credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_db() -> Iterator[Session]:
    """Yield a session, committing on success and rolling back on error."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer access token."""
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise _UNAUTHORIZED
    token = authorization[len(prefix) :]
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise _UNAUTHORIZED from exc
    user = UserRepository(db).get(int(payload["sub"]))
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    if payload.get("ver") != user.token_version:
        raise _UNAUTHORIZED
    return user


def get_verified_user(user: User = Depends(get_current_user)) -> User:
    """Require the authenticated user to have a verified email address."""
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email address to continue.",
        )
    return user


def get_current_admin(user: User = Depends(get_verified_user)) -> User:
    """Require the authenticated user to be an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user
