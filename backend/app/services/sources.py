"""Source business logic."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.appliers import available_appliers, has_applier
from app.appliers.private_api_risk import (
    config_accepts_private_api_risk,
    private_api_risk_rejection_error,
    requires_private_api_risk_ack,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.source import Source
from app.repositories.sources import SourceRepository
from app.schemas.source import (
    JobPostingPreview,
    SourceCreate,
    SourceDetectRequest,
    SourceDetectResult,
    SourceTestRequest,
    SourceTestResult,
    SourceUpdate,
)
from app.scrapers import available_scrapers
from app.scrapers.url_detect import detect_source_from_url
from app.services.pipeline import PipelineService
from app.services.plan_limits import PlanLimitsService

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
        if data.auto_apply_enabled:
            self._validate_auto_apply(data.adapter_key, data.default_config)
        PlanLimitsService(self.session).require_can_add_source(user_id, data.adapter_key)
        source = Source(
            user_id=user_id,
            name=data.name,
            adapter_key=data.adapter_key,
            base_url=data.base_url,
            default_config=data.default_config,
            enabled=data.enabled,
            auto_apply_enabled=data.auto_apply_enabled,
        )
        return self.repo.add(source)

    def update(self, source_id: int, user_id: int, data: SourceUpdate) -> Source:
        source = self.get(source_id, user_id)
        fields = data.model_dump(exclude_unset=True)
        if "adapter_key" in fields:
            self._validate_adapter(fields["adapter_key"])
            PlanLimitsService(self.session).require_can_update_source_adapter(
                user_id, fields["adapter_key"]
            )
            if not has_applier(fields["adapter_key"]):
                source.auto_apply_enabled = False
        if fields.get("auto_apply_enabled") is True:
            adapter_key = fields.get("adapter_key", source.adapter_key)
            config = fields.get("default_config", source.default_config)
            self._validate_auto_apply(adapter_key, config)
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

    def detect(self, data: SourceDetectRequest) -> SourceDetectResult:
        """Infer adapter and defaults from a careers-page URL."""
        detected = detect_source_from_url(data.url, page_title=data.page_title)
        if detected is None:
            raise ValidationError(
                "Could not detect a supported job board from this URL. "
                "Supported: Greenhouse, Lever, Ashby, and Workday careers pages."
            )
        self._validate_adapter(detected.adapter_key)
        return SourceDetectResult(
            adapter_key=detected.adapter_key,
            suggested_name=detected.suggested_name,
            base_url=detected.base_url,
            default_config=detected.default_config,
            query_url=detected.query_url,
        )

    @staticmethod
    def _validate_adapter(adapter_key: str) -> None:
        if adapter_key not in available_scrapers():
            raise ValidationError(
                f"Unknown adapter_key '{adapter_key}'. Available: {available_scrapers()}"
            )

    @staticmethod
    def _validate_auto_apply(adapter_key: str, config: dict[str, Any] | None = None) -> None:
        if not has_applier(adapter_key):
            raise ValidationError(
                f"Adapter '{adapter_key}' does not support auto-apply. "
                f"Available: {available_appliers()}"
            )
        if requires_private_api_risk_ack(adapter_key) and not config_accepts_private_api_risk(
            config
        ):
            raise ValidationError(private_api_risk_rejection_error())
