"""Apply orchestration: load profile, credentials, and delegate to an applier."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.appliers import ApplyContext, ApplyResult, get_applier, has_applier
from app.core.exceptions import NotFoundError, ValidationError
from app.models.application_log import ApplicationLog
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.repositories.application_logs import ApplicationLogRepository
from app.repositories.sources import SourceRepository
from app.services.credentials import CredentialService
from app.services.profiles import ProfileService


class ApplyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = SourceRepository(session)
        self.application_logs = ApplicationLogRepository(session)

    def enqueue_apply(self, user_id: int, job_id: int) -> int:
        """Validate a live apply and return a queued application_log id."""
        job, _source = self._validate_apply_request(user_id, job_id, dry_run=False)
        if self.application_logs.get_pending_for_job(job.id) is not None:
            raise ValidationError("An application is already in progress for this job")

        log = self.application_logs.add(
            ApplicationLog(
                seen_job_id=job.id,
                status="queued",
                dry_run=False,
            )
        )
        return log.id

    def apply_to_job(
        self,
        user_id: int,
        job_id: int,
        *,
        dry_run: bool = False,
        cover_letter: str | None = None,
        application_log_id: int | None = None,
    ) -> ApplyResult:
        """Submit or preview an application for one seen job."""
        job, source = self._validate_apply_request(user_id, job_id, dry_run=dry_run)
        apply_profile = ProfileService(self.session).get_for_apply(user_id)

        config = {**source.default_config, **job.search.config}
        credentials = CredentialService(self.session).secret_for_source(user_id, source.id)

        existing_log: ApplicationLog | None = None
        if application_log_id is not None:
            existing_log = self._load_application_log(application_log_id, user_id, job.id)
            if existing_log.status not in ("queued", "processing"):
                raise ValidationError("This application is no longer queued")
            existing_log.status = "processing"
            self.session.flush()

        ctx = ApplyContext(
            job_external_id=job.external_id,
            job_title=job.title,
            company=job.company,
            job_url=job.url,
            config=config,
            profile=apply_profile,
            resume_file=apply_profile.resume_file,
            credentials=credentials,
            cover_letter=cover_letter,
            dry_run=dry_run,
        )
        result = get_applier(source.adapter_key).apply(ctx)

        if existing_log is not None:
            self._update_log(existing_log, result)
        else:
            self._record_attempt(job, result, dry_run=dry_run)

        if result.status == "submitted":
            job.status = "applied"
            self.session.flush()

        return result

    def fail_queued_apply(self, application_log_id: int, error: str) -> None:
        """Mark a queued apply as failed when the worker cannot complete it."""
        log = self.session.get(ApplicationLog, application_log_id)
        if log is None or log.status not in ("queued", "processing"):
            return
        log.status = "failed"
        log.error = error
        self.session.flush()

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

    def _record_attempt(self, job: SeenJob, result: ApplyResult, *, dry_run: bool) -> None:
        """Persist an audit row for every apply attempt."""
        self.application_logs.add(
            ApplicationLog(
                seen_job_id=job.id,
                status=result.status,
                dry_run=dry_run,
                error=result.error,
                payload=result.payload,
                external_application_id=result.external_application_id,
            )
        )

    def _update_log(self, log: ApplicationLog, result: ApplyResult) -> None:
        """Update an existing queued log with the final apply outcome."""
        log.status = result.status
        log.error = result.error
        log.payload = result.payload
        log.external_application_id = result.external_application_id
        self.session.flush()

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
