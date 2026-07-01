"""Application log endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.application_log import ApplicationLogRead
from app.services.application_logs import ApplicationLogService

router = APIRouter()


@router.get("", response_model=list[ApplicationLogRead])
def list_application_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> list[ApplicationLogRead]:
    """Return recent auto-apply attempts for the authenticated user."""
    return ApplicationLogService(db).list_for_user(user.id, limit=limit)


@router.get("/{log_id}", response_model=ApplicationLogRead)
def get_application_log(
    log_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> ApplicationLogRead:
    """Return one auto-apply attempt for polling queued submissions."""
    return ApplicationLogService(db).get_for_user(user.id, log_id)
