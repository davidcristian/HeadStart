"""Apply orchestration: load profile, credentials, and delegate to an applier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.appliers import ApplyContext, ApplyResult, get_applier, has_applier
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.application_log import ApplicationLog
from app.models.base import utcnow
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.repositories.application_logs import ApplicationLogRepository
from app.repositories.sources import SourceRepository
from app.schemas.profile import ResumeFile
from app.services.apply_tracking import application_tracking_payload
from app.services.credentials import CredentialService
from app.services.plan_limits import PlanLimitsService
from app.services.profiles import ProfileService
from app.services.tailored_resume import resolve_tailored_resume_for_apply

logger = get_logger(__name__)


@dataclass(frozen=True)
class QueuedAutoApply:
    """A live apply queued during the pipeline; dispatch after the DB commit."""

    application_log_id: int
    user_id: int
    job_id: int
    cover_letter: str | None


class ApplyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = SourceRepository(session)
        self.application_logs = ApplicationLogRepository(session)

    def enqueue_apply(self, user_id: int, job_id: int) -> int:
        """Validate a live apply and return a queued application_log id."""
        job, _source = self._validate_apply_request(user_id, job_id, dry_run=False)
        log = self._queue_live_apply(job)
        if log is None:
            raise ValidationError("An application is already in progress for this job")
        return log.id

    def enqueue_auto_apply_from_pipeline(
        self,
        user_id: int,
        job_id: int,
    ) -> QueuedAutoApply | None:
        """Queue a live apply when pipeline prerequisites are met; skip silently otherwise."""
        job = self._load_job(job_id, user_id)
        source = self.sources.get(job.search.source_id, user_id)
        if source is None or not self._pipeline_auto_apply_eligible(job, source, user_id):
            return None
        log = self._queue_live_apply(job)
        if log is None:
            return None

        logger.info(
            "pipeline auto-apply queued log=%s job=%s user=%s",
            log.id,
            job.id,
            user_id,
        )
        return QueuedAutoApply(log.id, user_id, job.id, None)

    def apply_to_job(
        self,
        user_id: int,
        job_id: int,
        *,
        dry_run: bool = False,
        cover_letter: str | None = None,
        tailored_resume_b64: str | None = None,
        tailored_resume_artifact_id: int | None = None,
        application_log_id: int | None = None,
    ) -> ApplyResult:
        """Submit or preview an application for one seen job."""
        job, source = self._validate_apply_request(user_id, job_id, dry_run=dry_run)
        apply_profile = ProfileService(self.session).get_for_apply(user_id)
        tailored_resume, artifact_id = resolve_tailored_resume_for_apply(
            self.session,
            user_id,
            tailored_resume_b64=tailored_resume_b64,
            tailored_resume_artifact_id=tailored_resume_artifact_id,
        )
        resume_file = tailored_resume or apply_profile.resume_file

        config = {**source.default_config, **job.search.config}
        credentials = CredentialService(self.session).secret_for_source(user_id, source.id)

        existing_log: ApplicationLog | None = None
        if application_log_id is not None:
            existing_log = self._load_application_log(application_log_id, user_id, job.id)
            if existing_log.status not in ("queued", "processing"):
                raise ValidationError("This application is no longer queued")
            # Prefer claim_queued_apply (committed before the external POST). If the
            # row is still queued (sync/tests), flip here inside this transaction.
            if existing_log.status == "queued":
                existing_log.status = "processing"
                self.session.flush()

        ctx = ApplyContext(
            job_external_id=job.external_id,
            job_title=job.title,
            company=job.company,
            job_url=job.url,
            config=config,
            profile=apply_profile,
            resume_file=resume_file,
            credentials=credentials,
            cover_letter=cover_letter,
            dry_run=dry_run,
        )
        result = get_applier(source.adapter_key).apply(ctx)

        if existing_log is not None:
            self._update_log(
                existing_log,
                job,
                result,
                tailored_resume=tailored_resume,
                artifact_id=artifact_id,
            )
        else:
            self._record_attempt(
                job,
                result,
                dry_run=dry_run,
                tailored_resume=tailored_resume,
                artifact_id=artifact_id,
            )

        if result.status == "submitted":
            job.status = "applied"
            job.applied_at = utcnow()
            self.session.flush()

        return result

    def _queue_live_apply(self, job: SeenJob) -> ApplicationLog | None:
        """Queue one live apply log, or None when another is already in-flight."""
        return self.application_logs.try_add_pending(
            ApplicationLog(
                seen_job_id=job.id,
                status="queued",
                dry_run=False,
                payload=application_tracking_payload(job),
            )
        )

    def _validate_apply_request(
        self,
        user_id: int,
        job_id: int,
        *,
        dry_run: bool,
    ) -> tuple[SeenJob, Source]:
        job = self._load_job(job_id, user_id)
        source = self.sources.get(job.search.source_id, user_id)
        if source is None:
            raise NotFoundError(f"Source {job.search.source_id} not found")

        if not has_applier(source.adapter_key):
            raise ValidationError(
                f"Source adapter '{source.adapter_key}' does not support auto-apply"
            )

        if not dry_run and not source.auto_apply_enabled:
            raise ValidationError(
                "Enable auto-apply on this source before submitting live applications"
            )

        apply_profile = ProfileService(self.session).get_for_apply(user_id)
        if not apply_profile.exists:
            raise ValidationError("Save an application profile before applying")

        return job, source

    def _record_attempt(
        self,
        job: SeenJob,
        result: ApplyResult,
        *,
        dry_run: bool,
        tailored_resume: ResumeFile | None = None,
        artifact_id: int | None = None,
    ) -> None:
        """Persist an audit row for every apply attempt."""
        self.application_logs.add(
            ApplicationLog(
                seen_job_id=job.id,
                status=result.status,
                dry_run=dry_run,
                error=result.error,
                payload=self._merge_tracking_payload(job, result.payload, tailored_resume),
                external_application_id=result.external_application_id,
                tailored_resume_artifact_id=artifact_id,
            )
        )

    def _update_log(
        self,
        log: ApplicationLog,
        job: SeenJob,
        result: ApplyResult,
        *,
        tailored_resume: ResumeFile | None = None,
        artifact_id: int | None = None,
    ) -> None:
        """Update an existing queued log with the final apply outcome."""
        log.status = result.status
        log.error = result.error
        log.payload = self._merge_tracking_payload(job, result.payload, tailored_resume)
        log.external_application_id = result.external_application_id
        log.tailored_resume_artifact_id = artifact_id
        self.session.flush()

    def _merge_tracking_payload(
        self,
        job: SeenJob,
        adapter_payload: dict[str, Any] | None,
        tailored_resume: ResumeFile | None = None,
    ) -> dict[str, Any]:
        tracking = application_tracking_payload(job)
        if tailored_resume is not None:
            tracking["tailored_resume"] = {
                "filename": tailored_resume.filename,
                "size_bytes": tailored_resume.size_bytes,
                "content_type": tailored_resume.content_type,
            }
        if not adapter_payload:
            return tracking
        return {**tracking, **adapter_payload}

    def _pipeline_auto_apply_eligible(
        self,
        job: SeenJob,
        source: Source,
        user_id: int,
    ) -> bool:
        if not source.auto_apply_enabled:
            return False
        if not has_applier(source.adapter_key):
            return False
        if not ProfileService(self.session).get_for_apply(user_id).exists:
            return False
        if not PlanLimitsService(self.session).allows_pipeline_auto_apply(user_id):
            logger.info(
                "pipeline auto-apply skipped (daily volume cap) job=%s user=%s",
                job.id,
                user_id,
            )
            return False
        return True

    def _load_application_log(
        self,
        log_id: int,
        user_id: int,
        seen_job_id: int,
    ) -> ApplicationLog:
        log = self.application_logs.get_for_user(log_id, user_id)
        if log is None or log.seen_job_id != seen_job_id:
            raise NotFoundError(f"Application log {log_id} not found")
        return log

    def _load_job(self, job_id: int, user_id: int) -> SeenJob:
        stmt = (
            select(SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(SeenJob.id == job_id, Search.user_id == user_id)
            .options(joinedload(SeenJob.search))
        )
        job = self.session.scalar(stmt)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        return job
