"""Source business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.source import Source
from app.repositories.sources import SourceRepository
from app.schemas.source import (
    JobPostingPreview,
    SourceCreate,
    SourceTestRequest,
    SourceTestResult,
    SourceUpdate,
)
from app.scrapers import available_scrapers
from app.services.pipeline import PipelineService

_PREVIEW_LIMIT = 5


class SourceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SourceRepository(session)

    def list_all(self, user_id: int) -> list[Source]:
        return self.repo.list_all(user_id)

    def get(self, source_id: int, user_id: int) -> Source:
        source = self.repo.get(source_id, user_id)
        if source is None:
            raise NotFoundError(f"Source {source_id} not found")
        return source

    def create(self, user_id: int, data: SourceCreate) -> Source:
        self._validate_adapter(data.adapter_key)
        source = Source(
            user_id=user_id,
            name=data.name,
            adapter_key=data.adapter_key,
            base_url=data.base_url,
            default_config=data.default_config,
            enabled=data.enabled,
        )
        return self.repo.add(source)

    def update(self, source_id: int, user_id: int, data: SourceUpdate) -> Source:
        source = self.get(source_id, user_id)
        fields = data.model_dump(exclude_unset=True)
        if "adapter_key" in fields:
            self._validate_adapter(fields["adapter_key"])
        for key, value in fields.items():
            setattr(source, key, value)
        self.session.flush()
        return source

    def delete(self, source_id: int, user_id: int) -> None:
        self.repo.delete(self.get(source_id, user_id))

    def test_scrape(
        self, source_id: int, user_id: int, data: SourceTestRequest
    ) -> SourceTestResult:
        """Scrape once with the source config and return sample postings."""
        source = self.get(source_id, user_id)
        query_url = source.base_url if data.query_url is None else data.query_url
        merged_config = {**source.default_config, **(data.config or {})}
        filters = data.filters or {}
        try:
            postings = PipelineService(self.session).scrape(
                adapter_key=source.adapter_key,
                user_id=user_id,
                source_id=source.id,
                query_url=query_url,
                filters=filters,
                config=merged_config,
            )
        except Exception as exc:  # adapters/network are untrusted
            return SourceTestResult(ok=False, error=str(exc))
        sample = [
            JobPostingPreview(
                external_id=p.external_id,
                title=p.title,
                company=p.company,
                location=p.location,
                url=p.url,
            )
            for p in postings[:_PREVIEW_LIMIT]
        ]
        return SourceTestResult(ok=True, found=len(postings), sample=sample)

    @staticmethod
    def _validate_adapter(adapter_key: str) -> None:
        if adapter_key not in available_scrapers():
            raise ValidationError(
                f"Unknown adapter_key '{adapter_key}'. Available: {available_scrapers()}"
            )
