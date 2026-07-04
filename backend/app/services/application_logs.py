"""Application log business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.repositories.application_logs import ApplicationLogRepository
from app.schemas.application_artifact import ApplicationArtifactMeta
from app.schemas.application_log import ApplicationLogRead

if TYPE_CHECKING:
    from app.models.application_log import ApplicationLog


class ApplicationLogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ApplicationLogRepository(session)

    def list_for_user(self, user_id: int, *, limit: int | None = 100) -> list[ApplicationLogRead]:
        """Return auto-apply attempts for the authenticated user."""
        logs = self.repo.list_recent_for_user(user_id, limit=limit)
        return [self._to_read(log) for log in logs]

    def get_for_user(self, user_id: int, log_id: int) -> ApplicationLogRead:
        """Return one application log scoped to the authenticated user."""
        log = self.repo.get_for_user(log_id, user_id)
        if log is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(f"Application log {log_id} not found")
        return self._to_read(log)

    def _to_read(self, log: ApplicationLog) -> ApplicationLogRead:
        artifact = log.tailored_resume_artifact
        return ApplicationLogRead(
            id=log.id,
            seen_job_id=log.seen_job_id,
            job_title=log.seen_job.title,
            job_company=log.seen_job.company,
            job_url=log.seen_job.url,
            status=log.status,
            dry_run=log.dry_run,
            error=log.error,
            payload=log.payload,
            external_application_id=log.external_application_id,
            tailored_resume_artifact=(
                ApplicationArtifactMeta.model_validate(artifact) if artifact is not None else None
            ),
            created_at=log.created_at,
        )
