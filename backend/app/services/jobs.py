"""Job feed read logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.seen_job import SeenJob
from app.repositories.jobs import SeenJobRepository
from app.schemas.job import JobUpdate


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SeenJobRepository(session)

    def list_all(
        self,
        *,
        user_id: int,
        search_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SeenJob]:
        return self.repo.list_all(
            user_id=user_id, search_id=search_id, status=status, limit=min(max(limit, 1), 500)
        )

    def update(self, job_id: int, user_id: int, data: JobUpdate) -> SeenJob:
        job = self.repo.get(job_id, user_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        job.status = data.status
        self.session.flush()
        return job
