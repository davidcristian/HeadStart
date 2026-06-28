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

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(User)) or 0)

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def update_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        self.session.flush()
        return user
