"""NotificationTarget business logic, including sending a test notification."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.notification_target import NotificationTarget
from app.notifiers import NotifyContext, available_notifiers, get_notifier
from app.notifiers.types import DeliveryResult
from app.repositories.targets import TargetRepository
from app.schemas.target import TargetCreate, TargetUpdate
from app.scrapers.types import JobPosting
from app.services.plan_limits import PlanLimitsService
from app.services.target_config import validate_target_config


class TargetService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = TargetRepository(session)

    def list_all(self, user_id: int) -> list[NotificationTarget]:
        return self.repo.list_all(user_id)

    def get(self, target_id: int, user_id: int) -> NotificationTarget:
        target = self.repo.get(target_id, user_id)
        if target is None:
            raise NotFoundError(f"Notification target {target_id} not found")
        return target

    def create(self, user_id: int, data: TargetCreate) -> NotificationTarget:
        self._validate_type(data.type)
        validate_target_config(data.type, data.config)
        PlanLimitsService(self.session).require_can_add_target(user_id, data.type)
        target = NotificationTarget(
            user_id=user_id, name=data.name, type=data.type, config=data.config
        )
        return self.repo.add(target)

    def update(self, target_id: int, user_id: int, data: TargetUpdate) -> NotificationTarget:
        target = self.get(target_id, user_id)
        fields = data.model_dump(exclude_unset=True)
        if "type" in fields:
            self._validate_type(fields["type"])
            PlanLimitsService(self.session).require_can_update_target_type(user_id, fields["type"])
        next_type = str(fields.get("type", target.type))
        next_config = fields.get("config", target.config)
        validate_target_config(next_type, next_config if isinstance(next_config, dict) else {})
        for key, value in fields.items():
            setattr(target, key, value)
        self.session.flush()
        return target

    def delete(self, target_id: int, user_id: int) -> None:
        self.repo.delete(self.get(target_id, user_id))

    def send_test(self, target_id: int, user_id: int) -> DeliveryResult:
        """Send a single example notification to verify the target works."""
        target = self.get(target_id, user_id)
        notifier = get_notifier(target.type)
        sample = JobPosting(
            external_id="test",
            title="HeadStart test notification",
            company="HeadStart",
            location="",
            url="https://github.com/",
        )
        results = notifier.send(
            NotifyContext(target_type=target.type, config=target.config), [sample]
        )
        return results[0]

    @staticmethod
    def _validate_type(target_type: str) -> None:
        if target_type not in available_notifiers():
            raise ValidationError(
                f"Unknown target type '{target_type}'. Available: {available_notifiers()}"
            )
