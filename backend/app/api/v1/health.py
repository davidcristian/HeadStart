"""Health + capability endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_current_user, get_db
from app.appliers import available_appliers
from app.core.config import settings
from app.models.user import User
from app.schemas.meta import HealthRead, MetaRead
from app.schemas.plan import AccountPlanRead
from app.services.plan_limits import PlanLimitsService

router = APIRouter()


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    """Public liveness/readiness probe (no auth)."""
    return HealthRead(status="ok", version=__version__, environment=settings.environment)


@router.get("/meta", response_model=MetaRead)
def meta(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MetaRead:
    """Capabilities used by the UI to populate adapter/notifier dropdowns."""
    limits = PlanLimitsService(db)
    snapshot = limits.snapshot(user)
    plan = AccountPlanRead.model_validate(snapshot)
    return MetaRead(
        scrapers=plan.allowed_scrapers,
        notifiers=plan.allowed_notifiers,
        appliers=available_appliers(),
        plan=plan,
    )
