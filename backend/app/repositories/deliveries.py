"""Data access for DeliveryLog."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.seen_job import SeenJob
from app.schemas.delivery import DeliveryFailureRead


class DeliveryLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: DeliveryLog) -> DeliveryLog:
        self.session.add(log)
        self.session.flush()
        return log

    def recent_failures_for_searches(
        self, search_ids: list[int], *, limit: int = 5
    ) -> dict[int, list[DeliveryFailureRead]]:
        """Return the most recent failed deliveries per search, newest first."""
        if not search_ids:
            return {}
        stmt = (
            select(DeliveryLog, SeenJob)
            .join(SeenJob, DeliveryLog.seen_job_id == SeenJob.id)
            .where(SeenJob.search_id.in_(search_ids))
            .where(DeliveryLog.status == "failed")
            .order_by(DeliveryLog.sent_at.desc())
        )
        by_search: dict[int, list[DeliveryFailureRead]] = {sid: [] for sid in search_ids}
        for log, job in self.session.execute(stmt).all():
            bucket = by_search[job.search_id]
            if len(bucket) >= limit:
                continue
            bucket.append(
                DeliveryFailureRead(
                    job_title=job.title,
                    job_url=job.url,
                    error=log.error,
                    sent_at=log.sent_at,
                )
            )
        return by_search
