"""Data access for User. Queries only — no business logic."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def bump_feed_token_version(self, user: User) -> User:
        """Invalidate existing RSS feed URLs by incrementing the token version."""
        user.feed_token_version += 1
        self.session.flush()
        return user

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(User)) or 0)

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def update_password(self, user: User, password_hash: str) -> User:
        """Update the stored password hash for a user."""
        user.password_hash = password_hash
        self.session.flush()
        return user

    def list_all(self) -> list[User]:
        """Return every user ordered by id (admin listing)."""
        return list(self.session.scalars(select(User).order_by(User.id)))

    def count_admins(self) -> int:
        """Count users with admin privileges."""
        return int(
            self.session.scalar(
                select(func.count()).select_from(User).where(User.is_admin.is_(True))
            )
            or 0
        )

    def update_flags(
        self, user: User, *, is_active: bool | None = None, is_admin: bool | None = None
    ) -> User:
        """Patch admin-managed account flags."""
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None:
            user.is_admin = is_admin
        self.session.flush()
        return user
