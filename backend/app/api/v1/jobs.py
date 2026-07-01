"""Job feed endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.job import JobApplyRequest, JobApplyResult, JobRead, JobStatus, JobUpdate
from app.services.apply import ApplyService
from app.services.jobs import JobService

router = APIRouter()


@router.get("", response_model=list[JobRead])
def list_jobs(
    search_id: int | None = Query(default=None),
    status: JobStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> list[JobRead]:
    jobs = JobService(db).list_all(user_id=user.id, search_id=search_id, status=status, limit=limit)
    return [JobRead.model_validate(j) for j in jobs]


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> JobRead:
    return JobRead.model_validate(JobService(db).update(job_id, user.id, data))


@router.post("/{job_id}/apply", response_model=JobApplyResult)
def apply_to_job(
    job_id: int,
    data: JobApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> JobApplyResult:
    """Submit or preview an auto-apply for one job."""
    result = ApplyService(db).apply_to_job(
        user.id,
        job_id,
        dry_run=data.dry_run,
        cover_letter=data.cover_letter,
    )
    job = None
    if result.status == "submitted":
        job = JobRead.model_validate(JobService(db).get(job_id, user.id))
    return JobApplyResult(
        status=result.status,
        error=result.error,
        payload=result.payload,
        external_application_id=result.external_application_id,
        job=job,
    )
