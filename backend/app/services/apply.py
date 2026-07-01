"""Apply orchestration: load profile, credentials, and delegate to an applier."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.appliers import ApplyContext, ApplyResult, get_applier, has_applier
from app.core.exceptions import NotFoundError, ValidationError
from app.models.application_log import ApplicationLog
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.repositories.application_logs import ApplicationLogRepository
from app.repositories.sources import SourceRepository
from app.services.credentials import CredentialService
from app.services.profiles import ProfileService


class ApplyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = SourceRepository(session)
        self.application_logs = ApplicationLogRepository(session)

    def apply_to_job(
        self,
        user_id: int,
        job_id: int,
        *,
        dry_run: bool = False,
        cover_letter: str | None = None,
    ) -> ApplyResult:
        """Submit or preview an application for one seen job."""
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

        profile = ProfileService(self.session).get(user_id)
        if not profile.exists:
            raise ValidationError("Save an application profile before applying")

        config = {**source.default_config, **job.search.config}
        credentials = CredentialService(self.session).secret_for_source(user_id, source.id)

        ctx = ApplyContext(
            job_external_id=job.external_id,
            job_title=job.title,
            company=job.company,
            job_url=job.url,
            config=config,
            profile=profile,
            credentials=credentials,
            cover_letter=cover_letter,
            dry_run=dry_run,
        )
        result = get_applier(source.adapter_key).apply(ctx)
        self._record_attempt(job, result, dry_run=dry_run)

        if result.status == "submitted":
            job.status = "applied"
            self.session.flush()

        return result

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
