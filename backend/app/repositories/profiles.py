"""Data access for ApplicationProfile. Queries only — no business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application_profile import ApplicationProfile


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> ApplicationProfile | None:
        return self.session.scalar(
            select(ApplicationProfile).where(ApplicationProfile.user_id == user_id)
        )

    def add(self, profile: ApplicationProfile) -> ApplicationProfile:
        self.session.add(profile)
        self.session.flush()
        return profile

    def delete(self, profile: ApplicationProfile) -> None:
        self.session.delete(profile)
