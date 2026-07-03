"""Health + capability endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_db, get_verified_user
from app.appliers import available_appliers
from app.core.config import settings
from app.inbox import available_mailboxes
from app.models.user import User
from app.schemas.meta import AdsConfigRead, HealthRead, MetaRead
from app.schemas.plan import AccountPlanRead
from app.services.plan_limits import PlanLimitsService

router = APIRouter()


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    """Public liveness/readiness probe (no auth)."""
    return HealthRead(status="ok", version=__version__, environment=settings.environment)


@router.get("/meta", response_model=MetaRead)
def meta(user: User = Depends(get_verified_user), db: Session = Depends(get_db)) -> MetaRead:
    """Capabilities used by the UI to populate adapter/notifier dropdowns."""
    limits = PlanLimitsService(db)
    snapshot = limits.snapshot(user)
    if not settings.ads_enabled:
        snapshot = {**snapshot, "show_ads": False}
    plan = AccountPlanRead.model_validate(snapshot)
    ads_slot: str | None = None
    if settings.ads_enabled and plan.show_ads:
        ads_slot = settings.ads_external_slot_url.strip() or None
    return MetaRead(
        scrapers=plan.allowed_scrapers,
        notifiers=plan.allowed_notifiers,
        appliers=available_appliers(),
        mailboxes=available_mailboxes(),
        inbox_agent_enabled=settings.inbox_agent_enabled,
        plan=plan,
        ads=AdsConfigRead(external_slot_url=ads_slot),
    )
