"""Application log business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.application_logs import ApplicationLogRepository
from app.schemas.application_log import ApplicationLogRead


class ApplicationLogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ApplicationLogRepository(session)

    def list_for_user(self, user_id: int, *, limit: int = 100) -> list[ApplicationLogRead]:
        """Return recent auto-apply attempts for the authenticated user."""
        logs = self.repo.list_recent_for_user(user_id, limit=limit)
        return [
            ApplicationLogRead(
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
                created_at=log.created_at,
            )
            for log in logs
        ]
