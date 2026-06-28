"""Health + capability endpoints."""

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.notifiers import available_notifiers
from app.schemas.meta import HealthRead, MetaRead
from app.scrapers import available_scrapers

router = APIRouter()


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    """Public liveness/readiness probe (no auth)."""
    return HealthRead(status="ok", version=__version__, environment=settings.environment)


@router.get("/meta", response_model=MetaRead)
def meta(_: User = Depends(get_current_user)) -> MetaRead:
    """Capabilities used by the UI to populate adapter/notifier dropdowns."""
    return MetaRead(scrapers=available_scrapers(), notifiers=available_notifiers())
