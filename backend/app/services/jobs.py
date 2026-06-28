"""Job feed read logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.seen_job import SeenJob
from app.repositories.jobs import SeenJobRepository


class JobService:
    def __init__(self, session: Session) -> None:
        self.repo = SeenJobRepository(session)

    def list_all(
        self, *, user_id: int, search_id: int | None = None, limit: int = 100
    ) -> list[SeenJob]:
        return self.repo.list_all(
            user_id=user_id, search_id=search_id, limit=min(max(limit, 1), 500)
        )
