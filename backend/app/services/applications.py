"""Application pipeline aggregation for the /applications view."""

from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.repositories.applications import ApplicationPipelineRepository
from app.schemas.application_pipeline import (
    ApplicationAttemptSummary,
    ApplicationPipelineRead,
    ApplicationPipelineStage,
)
from app.schemas.job import JobStatus


def live_attempts(logs: list[ApplicationLog]) -> list[ApplicationLog]:
    """Return non-preview application logs sorted oldest-first."""
    return sorted((log for log in logs if not log.dry_run), key=lambda row: row.created_at)


def latest_live_attempt(logs: list[ApplicationLog]) -> ApplicationLog | None:
    """Return the most recent live apply attempt, if any."""
    attempts = live_attempts(logs)
    return attempts[-1] if attempts else None


def derive_pipeline_stage(job: SeenJob, latest: ApplicationLog | None) -> ApplicationPipelineStage:
    """Map job + latest live attempt to a pipeline stage for the UI."""
    if job.status == "archived":
        return "archived"
    if job.status == "closed":
        return "closed"
    if latest is not None and latest.status in ("queued", "processing"):
        return "queued"
    if latest is not None and latest.status == "failed":
        return "apply_failed"
    if job.status == "applied" or (latest is not None and latest.status == "submitted"):
        return "awaiting_reply"
    return "awaiting_reply"


class ApplicationPipelineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ApplicationPipelineRepository(session)

    def list_for_user(
        self,
        user_id: int,
        *,
        stage: ApplicationPipelineStage | None = None,
        limit: int = 100,
    ) -> list[ApplicationPipelineRead]:
        """Return pipeline rows for jobs with live apply activity."""
        jobs = self.repo.list_jobs_for_user(user_id, limit=limit)
        rows = [self._to_read(job) for job in jobs]
        if stage is None:
            return rows
        return [row for row in rows if row.pipeline_stage == stage]

    def _to_read(self, job: SeenJob) -> ApplicationPipelineRead:
        attempts = live_attempts(job.application_logs)
        latest = attempts[-1] if attempts else None
        return ApplicationPipelineRead(
            job_id=job.id,
            search_id=job.search_id,
            title=job.title,
            company=job.company,
            location=job.location,
            url=job.url,
            job_status=cast(JobStatus, job.status),
            pipeline_stage=derive_pipeline_stage(job, latest),
            applied_at=job.applied_at,
            latest_attempt=self._attempt_summary(latest),
            attempts=[self._attempt_summary(log) for log in attempts],
        )

    def _attempt_summary(self, log: ApplicationLog | None) -> ApplicationAttemptSummary | None:
        if log is None:
            return None
        return ApplicationAttemptSummary.model_validate(log)
