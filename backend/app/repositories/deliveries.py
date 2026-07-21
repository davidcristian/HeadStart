"""Data access for DeliveryLog."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.schemas.delivery import DeliveryFailureRead


class DeliveryLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: DeliveryLog) -> DeliveryLog:
        self.session.add(log)
        self.session.flush()
        return log

    def list_all_for_user(self, user_id: int) -> list[DeliveryLog]:
        """Return every delivery attempt for jobs owned by the user."""
        stmt = (
            select(DeliveryLog)
            .join(SeenJob, DeliveryLog.seen_job_id == SeenJob.id)
            .join(Search, SeenJob.search_id == Search.id)
            .where(Search.user_id == user_id)
            .order_by(DeliveryLog.sent_at.desc())
        )
        return list(self.session.scalars(stmt))

    def recent_failures_for_searches(
        self, search_ids: list[int], *, limit: int = 5
    ) -> dict[int, list[DeliveryFailureRead]]:
        """Return the most recent failed deliveries per search, newest first."""
        if not search_ids:
            return {}
        # Rank in SQL so search-status never materializes a search's full
        # failure history just to show the newest N rows.
        ranked = (
            select(
                DeliveryLog.id.label("log_id"),
                SeenJob.id.label("job_id"),
                func.row_number()
                .over(
                    partition_by=SeenJob.search_id,
                    order_by=DeliveryLog.sent_at.desc(),
                )
                .label("rn"),
            )
            .join(SeenJob, DeliveryLog.seen_job_id == SeenJob.id)
            .where(SeenJob.search_id.in_(search_ids))
            .where(DeliveryLog.status == "failed")
        ).subquery()
        stmt = (
            select(DeliveryLog, SeenJob)
            .join(ranked, DeliveryLog.id == ranked.c.log_id)
            .join(SeenJob, SeenJob.id == ranked.c.job_id)
            .where(ranked.c.rn <= limit)
            .order_by(DeliveryLog.sent_at.desc())
        )
        by_search: dict[int, list[DeliveryFailureRead]] = {sid: [] for sid in search_ids}
        for log, job in self.session.execute(stmt).all():
            by_search[job.search_id].append(
                DeliveryFailureRead(
                    job_title=job.title,
                    job_url=job.url,
                    error=log.error,
                    sent_at=log.sent_at,
                )
            )
        return by_search
