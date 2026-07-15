"""Application pipeline aggregation for the /applications view."""

from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from app.models.application_log import ApplicationLog
from app.models.seen_job import SeenJob
from app.repositories.applications import ApplicationPipelineRepository
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_reply_drafts import InboxReplyDraftRepository
from app.schemas.application_artifact import ApplicationArtifactMeta
from app.schemas.application_pipeline import (
    ApplicationAttemptSummary,
    ApplicationPipelineRead,
    ApplicationPipelineStage,
)
from app.schemas.inbox_reply_draft import ReplyDraftSummary
from app.schemas.job import JobStatus


def live_attempts(logs: list[ApplicationLog]) -> list[ApplicationLog]:
    """Return non-preview application logs sorted oldest-first."""
    return sorted((log for log in logs if not log.dry_run), key=lambda row: row.created_at)


def latest_live_attempt(logs: list[ApplicationLog]) -> ApplicationLog | None:
    """Return the most recent live apply attempt, if any."""
    attempts = live_attempts(logs)
    return attempts[-1] if attempts else None


def derive_pipeline_stage(job: SeenJob, latest: ApplicationLog | None) -> ApplicationPipelineStage:
    """Map job + latest live attempt to a pipeline stage for the UI.

    Explicit stages cover archived/closed/rejected/interview_pending/ghosted/
    queued/apply_failed. Everything else (applied/submitted, recovered ghosts,
    or no live attempt yet) is ``awaiting_reply`` — there is no distinct
    post-submit stage.
    """
    if job.status == "archived":
        return "archived"
    if job.status == "closed":
        return "closed"
    if job.recruiter_rejection_at is not None:
        return "rejected"
    if job.interview_pending_at is not None:
        return "interview_pending"
    if job.ghosted_at is not None:
        return "ghosted"
    if latest is not None and latest.status in ("queued", "processing"):
        return "queued"
    if latest is not None and latest.status == "failed":
        return "apply_failed"
    return "awaiting_reply"


class ApplicationPipelineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ApplicationPipelineRepository(session)
        self.reply_drafts = InboxReplyDraftRepository(session)
        self.classifications = InboxClassificationRepository(session)

    def list_for_user(
        self,
        user_id: int,
        *,
        stage: ApplicationPipelineStage | None = None,
        limit: int = 100,
    ) -> list[ApplicationPipelineRead]:
        """Return pipeline rows for jobs with live apply activity."""
        jobs = self.repo.list_jobs_for_user(user_id, limit=limit)
        job_ids = [job.id for job in jobs]
        latest_drafts = self.reply_drafts.latest_by_seen_job_ids(user_id, job_ids)
        draftable = self.classifications.latest_draftable_by_seen_job_ids(user_id, job_ids)
        rows = [
            self._to_read(
                job,
                latest_drafts.get(job.id),
                draftable.get(job.id),
            )
            for job in jobs
        ]
        if stage is None:
            return rows
        return [row for row in rows if row.pipeline_stage == stage]

    def _to_read(
        self,
        job: SeenJob,
        draft: object | None = None,
        draftable_classification: object | None = None,
    ) -> ApplicationPipelineRead:
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
            ghosted_at=job.ghosted_at,
            ghost_recovered_at=job.ghost_recovered_at,
            interview_pending_at=job.interview_pending_at,
            recruiter_rejection_at=job.recruiter_rejection_at,
            latest_attempt=self._attempt_summary(latest),
            attempts=[self._attempt_summary(log) for log in attempts],
            latest_reply_draft=self._draft_summary(draft),
            latest_draftable_classification_id=self._classification_id(draftable_classification),
        )

    def _classification_id(self, classification: object | None) -> int | None:
        from app.models.inbox_classification import InboxClassification

        if isinstance(classification, InboxClassification):
            return classification.id
        return None

    def _draft_summary(self, draft: object | None) -> ReplyDraftSummary | None:
        if draft is None:
            return None
        from app.models.inbox_reply_draft import InboxReplyDraft

        if not isinstance(draft, InboxReplyDraft):
            return None
        return ReplyDraftSummary(
            id=draft.id,
            classification_id=draft.inbox_classification_id,
            subject=draft.subject,
            body_text=draft.body_text,
            provider=draft.provider,
            created_at=draft.created_at,
        )

    def _attempt_summary(self, log: ApplicationLog | None) -> ApplicationAttemptSummary | None:
        if log is None:
            return None
        artifact = log.tailored_resume_artifact
        return ApplicationAttemptSummary(
            id=log.id,
            status=log.status,
            error=log.error,
            external_application_id=log.external_application_id,
            tailored_resume_artifact=(
                ApplicationArtifactMeta.model_validate(artifact) if artifact is not None else None
            ),
            created_at=log.created_at,
        )
