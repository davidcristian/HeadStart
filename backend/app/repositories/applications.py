"""Data access for the application pipeline view."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.application_log import ApplicationLog
from app.models.search import Search
from app.models.seen_job import SeenJob


class ApplicationPipelineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_jobs_for_user(self, user_id: int, *, limit: int = 100) -> list[SeenJob]:
        """Return jobs with live apply activity or an applied triage status."""
        live_attempt_job_ids = (
            select(ApplicationLog.seen_job_id).where(ApplicationLog.dry_run.is_(False)).distinct()
        )
        stmt = (
            select(SeenJob)
            .join(Search, SeenJob.search_id == Search.id)
            .where(
                Search.user_id == user_id,
                or_(
                    SeenJob.status.in_(("applied", "archived", "closed")),
                    SeenJob.id.in_(live_attempt_job_ids),
                ),
            )
            .options(
                joinedload(SeenJob.application_logs).joinedload(
                    ApplicationLog.tailored_resume_artifact
                ),
                joinedload(SeenJob.search),
            )
            .order_by(SeenJob.applied_at.desc().nullslast(), SeenJob.first_seen_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique())
