"""Application pipeline endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.application_pipeline import ApplicationPipelineRead, ApplicationPipelineStage
from app.services.applications import ApplicationPipelineService

router = APIRouter()


@router.get("", response_model=list[ApplicationPipelineRead])
def list_applications(
    stage: ApplicationPipelineStage | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> list[ApplicationPipelineRead]:
    """Return jobs in the application pipeline with derived stage and attempt timeline."""
    return ApplicationPipelineService(db).list_for_user(user.id, stage=stage, limit=limit)
