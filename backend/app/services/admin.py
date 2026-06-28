"""Admin business logic: user management and global stats."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.admin_stats import AdminStatsRepository
from app.repositories.users import UserRepository
from app.schemas.admin import AdminStatsRead, AdminUserRead, AdminUserUpdate


class AdminService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.stats_repo = AdminStatsRepository(session)

    def list_users(self) -> list[AdminUserRead]:
        """Return every account for the admin dashboard."""
        return [AdminUserRead.model_validate(user) for user in self.users.list_all()]

    def update_user(self, user_id: int, actor_id: int, data: AdminUserUpdate) -> AdminUserRead:
        """Change account flags with safeguards against locking out the operator."""
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if data.is_active is False and user.id == actor_id:
            raise ValidationError("You cannot deactivate your own account.")
        if data.is_admin is False and user.id == actor_id:
            raise ValidationError("You cannot remove your own admin privileges.")
        if data.is_admin is False and user.is_admin and self.users.count_admins() <= 1:
            raise ValidationError("At least one admin account must remain.")

        updated = self.users.update_flags(
            user,
            is_active=data.is_active,
            is_admin=data.is_admin,
        )
        return AdminUserRead.model_validate(updated)

    def get_stats(self) -> AdminStatsRead:
        """Return aggregate scrape and delivery health across all users."""
        return self.stats_repo.get_stats()
