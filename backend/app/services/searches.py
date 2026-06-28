"""Search business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.base import utcnow
from app.models.search import Search
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.schemas.search import SearchCreate, SearchUpdate


class SearchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SearchRepository(session)
        self.sources = SourceRepository(session)
        self.targets = TargetRepository(session)

    def list_all(self, user_id: int) -> list[Search]:
        return self.repo.list_all(user_id)

    def get(self, search_id: int, user_id: int) -> Search:
        search = self.repo.get(search_id, user_id)
        if search is None:
            raise NotFoundError(f"Search {search_id} not found")
        return search

    def create(self, user_id: int, data: SearchCreate) -> Search:
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
            enabled=data.enabled,
            next_run_at=utcnow(),  # due immediately
        )
        return self.repo.add(search)

    def update(self, search_id: int, user_id: int, data: SearchUpdate) -> Search:
        search = self.get(search_id, user_id)
        fields = data.model_dump(exclude_unset=True)
        if "target_id" in fields and fields["target_id"] is not None:
            self._validate_refs(user_id, search.source_id, fields["target_id"])
        for key, value in fields.items():
            setattr(search, key, value)
        self.session.flush()
        return search

    def delete(self, search_id: int, user_id: int) -> None:
        self.repo.delete(self.get(search_id, user_id))

    def mark_due(self, search_id: int, user_id: int) -> Search:
        """Make a search due now so it is picked up on the next scheduler tick."""
        search = self.get(search_id, user_id)
        search.next_run_at = utcnow()
        self.session.flush()
        return search

    def _validate_refs(self, user_id: int, source_id: int, target_id: int | None) -> None:
        if self.sources.get(source_id, user_id) is None:
            raise ValidationError(f"Source {source_id} does not exist")
        if target_id is not None and self.targets.get(target_id, user_id) is None:
            raise ValidationError(f"Notification target {target_id} does not exist")
