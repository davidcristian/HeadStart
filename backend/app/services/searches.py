"""Search business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.base import utcnow
from app.models.search import Search
from app.repositories.deliveries import DeliveryLogRepository
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.schemas.search import SearchCreate, SearchRead, SearchRunRead, SearchUpdate
from app.services.pipeline import PipelineService
from app.services.plan_limits import PlanLimitsService


class SearchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SearchRepository(session)
        self.sources = SourceRepository(session)
        self.targets = TargetRepository(session)

    def list_all(self, user_id: int) -> list[Search]:
        return self.repo.list_all(user_id)

    def list_reads(self, user_id: int) -> list[SearchRead]:
        return self._to_reads(self.list_all(user_id))

    def get(self, search_id: int, user_id: int) -> Search:
        search = self.repo.get(search_id, user_id)
        if search is None:
            raise NotFoundError(f"Search {search_id} not found")
        return search

    def get_read(self, search_id: int, user_id: int) -> SearchRead:
        return self._to_reads([self.get(search_id, user_id)])[0]

    def create(self, user_id: int, data: SearchCreate) -> Search:
        PlanLimitsService(self.session).require_can_add_search(user_id)
        if data.notification_mode == "digest":
            PlanLimitsService(self.session).require_digest_mode(user_id)
        self._validate_refs(user_id, data.source_id, data.target_id)
        search = Search(
            user_id=user_id,
            name=data.name,
            source_id=data.source_id,
            target_id=data.target_id,
            query_url=data.query_url,
            filters=data.filters,
            config=data.config,
            interval_seconds=data.interval_seconds,
            notification_mode=data.notification_mode,
            digest_interval_seconds=data.digest_interval_seconds,
            enabled=data.enabled,
            next_run_at=utcnow(),  # due immediately
        )
        return self.repo.add(search)

    def create_read(self, user_id: int, data: SearchCreate) -> SearchRead:
        return self._to_reads([self.create(user_id, data)])[0]

    def update(self, search_id: int, user_id: int, data: SearchUpdate) -> Search:
        search = self.get(search_id, user_id)
        fields = data.model_dump(exclude_unset=True)
        if fields.get("notification_mode") == "digest":
            PlanLimitsService(self.session).require_digest_mode(user_id)
        if "target_id" in fields and fields["target_id"] is not None:
            self._validate_refs(user_id, search.source_id, fields["target_id"])
        for key, value in fields.items():
            setattr(search, key, value)
        self.session.flush()
        return search

    def update_read(self, search_id: int, user_id: int, data: SearchUpdate) -> SearchRead:
        return self._to_reads([self.update(search_id, user_id, data)])[0]

    def delete(self, search_id: int, user_id: int) -> None:
        self.repo.delete(self.get(search_id, user_id))

    def run_now(self, search_id: int, user_id: int) -> SearchRunRead:
        """Run the full pipeline immediately and return its outcome."""
        self.get(search_id, user_id)
        result = PipelineService(self.session).run(search_id)
        return SearchRunRead(
            search_id=result.search_id,
            found=result.found,
            new=result.new,
            notified=result.notified,
            failed=result.failed,
            skipped=result.skipped,
            filtered=result.filtered,
            queued=result.queued,
            closed=result.closed,
            error=result.error,
        )

    def _validate_refs(self, user_id: int, source_id: int, target_id: int | None) -> None:
        if self.sources.get(source_id, user_id) is None:
            raise ValidationError(f"Source {source_id} does not exist")
        if target_id is not None and self.targets.get(target_id, user_id) is None:
            raise ValidationError(f"Notification target {target_id} does not exist")

    def _to_reads(self, searches: list[Search]) -> list[SearchRead]:
        failures = DeliveryLogRepository(self.session).recent_failures_for_searches(
            [s.id for s in searches]
        )
        return [
            SearchRead.model_validate(s).model_copy(
                update={"recent_delivery_failures": failures.get(s.id, [])}
            )
            for s in searches
        ]
