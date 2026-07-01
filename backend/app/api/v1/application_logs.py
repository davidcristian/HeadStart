"""Application log endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.application_log import ApplicationLogRead
from app.services.application_logs import ApplicationLogService

router = APIRouter()


@router.get("", response_model=list[ApplicationLogRead])
def list_application_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApplicationLogRead]:
    """Return recent auto-apply attempts for the authenticated user."""
    return ApplicationLogService(db).list_for_user(user.id, limit=limit)
