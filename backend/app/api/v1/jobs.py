"""Job feed endpoint (read-only)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.job import JobRead
from app.services.jobs import JobService

router = APIRouter()


@router.get("", response_model=list[JobRead])
def list_jobs(
    search_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JobRead]:
    jobs = JobService(db).list_all(user_id=user.id, search_id=search_id, limit=limit)
    return [JobRead.model_validate(j) for j in jobs]
