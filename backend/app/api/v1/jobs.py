"""Job feed endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.appliers import ApplyResult
from app.models.user import User
from app.schemas.job import (
    JobApplyRequest,
    JobApplyResult,
    JobCoverLetterResult,
    JobRead,
    JobResumeResult,
    JobStatus,
    JobUpdate,
)
from app.services.apply import ApplyService
from app.services.cover_letters import CoverLetterService
from app.services.jobs import JobService
from app.services.resumes import ResumeService
from app.worker.tasks import apply_to_job_task

router = APIRouter()


def _apply_result_from_service(
    db: Session,
    user_id: int,
    job_id: int,
    result: ApplyResult,
) -> JobApplyResult:
    job = None
    if result.status == "submitted":
        job = JobRead.model_validate(JobService(db).get(job_id, user_id))
    return JobApplyResult(
        status=result.status,
        error=result.error,
        payload=result.payload,
        external_application_id=result.external_application_id,
        job=job,
    )


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


@router.post("/{job_id}/generate-cover-letter", response_model=JobCoverLetterResult)
def generate_cover_letter(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> JobCoverLetterResult:
    """Draft a tailored cover letter for one job using the user's profile."""
    result = CoverLetterService(db).generate(user.id, job_id)
    return JobCoverLetterResult.model_validate(result)


@router.post("/{job_id}/generate-resume", response_model=JobResumeResult)
def generate_resume(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> JobResumeResult:
    """Generate a tailored resume PDF for one job from the user's LaTeX template."""
    result = ResumeService(db).generate(user.id, job_id)
    return JobResumeResult.model_validate(result)


@router.post("/{job_id}/apply", response_model=JobApplyResult)
def apply_to_job(
    job_id: int,
    data: JobApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> JobApplyResult:
    """Submit or preview an auto-apply for one job."""
    service = ApplyService(db)
    if data.dry_run:
        result = service.apply_to_job(
            user.id,
            job_id,
            dry_run=True,
            cover_letter=data.cover_letter,
            tailored_resume_b64=data.tailored_resume_b64,
            tailored_resume_artifact_id=data.tailored_resume_artifact_id,
        )
        return _apply_result_from_service(db, user.id, job_id, result)

    log_id = service.enqueue_apply(user.id, job_id)
    # Commit before enqueue so the worker can see the queued log row immediately.
    db.commit()
    apply_to_job_task.delay(
        log_id,
        user.id,
        job_id,
        data.cover_letter,
        data.tailored_resume_b64,
        data.tailored_resume_artifact_id,
    )
    return JobApplyResult(status="queued", application_log_id=log_id)
