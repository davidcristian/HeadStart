"""Cross-table queries for the admin dashboard."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.models.user import User
from app.schemas.admin import AdminSearchErrorRead, AdminStatsRead


class AdminStatsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_stats(self, *, recent_error_limit: int = 10) -> AdminStatsRead:
        """Aggregate global counts and the most recent scrape errors."""
        users_total = int(self.session.scalar(select(func.count()).select_from(User)) or 0)
        users_active = int(
            self.session.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
            or 0
        )
        searches_total = int(self.session.scalar(select(func.count()).select_from(Search)) or 0)
        searches_enabled = int(
            self.session.scalar(
                select(func.count()).select_from(Search).where(Search.enabled.is_(True))
            )
            or 0
        )
        searches_with_error = int(
            self.session.scalar(
                select(func.count())
                .select_from(Search)
                .where(Search.last_error.is_not(None))
                .where(Search.last_error != "")
            )
            or 0
        )
        sources_total = int(self.session.scalar(select(func.count()).select_from(Source)) or 0)
        seen_jobs_total = int(self.session.scalar(select(func.count()).select_from(SeenJob)) or 0)
        deliveries_sent = int(
            self.session.scalar(
                select(func.count()).select_from(DeliveryLog).where(DeliveryLog.status == "sent")
            )
            or 0
        )
        deliveries_failed = int(
            self.session.scalar(
                select(func.count()).select_from(DeliveryLog).where(DeliveryLog.status == "failed")
            )
            or 0
        )

        error_rows = self.session.execute(
            select(Search, User.email)
            .join(User, Search.user_id == User.id)
            .where(Search.last_error.is_not(None))
            .where(Search.last_error != "")
            .order_by(Search.last_run_at.desc().nullslast(), Search.id.desc())
            .limit(recent_error_limit)
        ).all()
        recent_errors = [
            AdminSearchErrorRead(
                search_id=search.id,
                search_name=search.name,
                user_email=email,
                last_error=search.last_error or "",
                last_run_at=search.last_run_at,
            )
            for search, email in error_rows
        ]

        return AdminStatsRead(
            users_total=users_total,
            users_active=users_active,
            searches_total=searches_total,
            searches_enabled=searches_enabled,
            searches_with_error=searches_with_error,
            sources_total=sources_total,
            seen_jobs_total=seen_jobs_total,
            deliveries_sent=deliveries_sent,
            deliveries_failed=deliveries_failed,
            recent_errors=recent_errors,
        )
