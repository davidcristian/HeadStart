"""Data access for NotificationTarget."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_target import NotificationTarget


class TargetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, user_id: int) -> list[NotificationTarget]:
        return list(
            self.session.scalars(
                select(NotificationTarget)
                .where(NotificationTarget.user_id == user_id)
                .order_by(NotificationTarget.id)
            )
        )

    def get(self, target_id: int, user_id: int) -> NotificationTarget | None:
        return self.session.scalar(
            select(NotificationTarget).where(
                NotificationTarget.id == target_id,
                NotificationTarget.user_id == user_id,
            )
        )

    def add(self, target: NotificationTarget) -> NotificationTarget:
        self.session.add(target)
        self.session.flush()
        return target

    def delete(self, target: NotificationTarget) -> None:
        self.session.delete(target)
