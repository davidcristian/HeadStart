"""Cross-portal job search and bulk alert setup for curated employer boards."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import PlanLimitError, ValidationError
from app.core.plans import PlanId, scraper_allowed
from app.models.search import Search
from app.models.source import Source
from app.models.user import User
from app.portals.catalog import PortalPreset, get_portal_preset, list_portal_presets
from app.repositories.sources import SourceRepository
from app.schemas.portal import (
    PortalJobRead,
    PortalSearchErrorRead,
    PortalSearchRequest,
    PortalSearchResultRead,
    PortalSubscribeRequest,
    PortalSubscribeResultRead,
)
from app.schemas.search import SearchCreate
from app.schemas.source import SourceCreate
from app.services.pipeline import PipelineService
from app.services.plan_limits import PlanLimitsService
from app.services.portals import PortalCatalogService
from app.services.posting_filters import apply_posting_filters
from app.services.searches import SearchService
from app.services.sources import SourceService

_MAX_PER_PORTAL = 10
_MAX_TOTAL = 100


class PortalSearchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.limits = PlanLimitsService(session)
        self.sources = SourceRepository(session)
        self.pipeline = PipelineService(session)

    def search(self, user: User, data: PortalSearchRequest) -> PortalSearchResultRead:
        """Scrape curated portals once and return keyword-filtered matches."""
        self.limits.require_portal_search(user)
        plan = self.limits.resolve_plan(user)
        owned = self.sources.list_all(user.id)
        presets = _resolve_presets(plan, category=data.category, portal_ids=data.portal_ids)
        filters = _build_filters(data)
        items: list[PortalJobRead] = []
        errors: list[PortalSearchErrorRead] = []
        for preset in presets:
            if len(items) >= _MAX_TOTAL:
                break
            try:
                source_id = _source_id_for_preset(preset, owned)
                postings = self.pipeline.scrape(
                    adapter_key=preset.adapter_key,
                    user_id=user.id,
                    source_id=source_id or 0,
                    query_url=preset.base_url,
                    filters=filters,
                    config=dict(preset.default_config),
                )
                filtered, _removed = apply_posting_filters(postings, filters)
                for posting in filtered[:_MAX_PER_PORTAL]:
                    items.append(
                        PortalJobRead(
                            portal_id=preset.id,
                            company_name=preset.company_name,
                            external_id=posting.external_id,
                            title=posting.title,
                            location=posting.location,
                            url=posting.url,
                        )
                    )
                    if len(items) >= _MAX_TOTAL:
                        break
            except Exception as exc:  # adapters/network are untrusted
                errors.append(
                    PortalSearchErrorRead(
                        portal_id=preset.id,
                        company_name=preset.company_name,
                        error=str(exc),
                    )
                )
        return PortalSearchResultRead(
            items=items,
            portals_searched=len(presets),
            portals_failed=len(errors),
            errors=errors,
        )

    def subscribe(self, user: User, data: PortalSubscribeRequest) -> PortalSubscribeResultRead:
        """Ensure sources exist and create one search per curated portal."""
        self.limits.require_portal_search(user)
        plan = self.limits.resolve_plan(user)
        presets = _resolve_subscribe_presets(data, plan)
        filters = _build_filters(data)
        source_service = SourceService(self.session)
        search_service = SearchService(self.session)
        owned = self.sources.list_all(user.id)
        existing_searches = search_service.list_all(user.id)

        sources_created = 0
        searches_created = 0
        search_ids: list[int] = []
        skipped: list[str] = []
        limit_message: str | None = None

        for preset in presets:
            try:
                source, created = _ensure_source(
                    user.id,
                    preset,
                    owned=owned,
                    source_service=source_service,
                    limits=self.limits,
                )
                if created:
                    sources_created += 1
                    owned.append(source)

                if _has_matching_search(existing_searches, source.id, filters):
                    skipped.append(preset.id)
                    continue

                self.limits.require_can_add_search(user.id)
                if data.notification_mode == "digest":
                    self.limits.require_digest_mode(user.id)

                search = search_service.create(
                    user.id,
                    SearchCreate(
                        name=f"{data.keywords.strip()} at {preset.company_name}",
                        source_id=source.id,
                        target_id=data.target_id,
                        query_url=preset.base_url,
                        filters=filters,
                        interval_seconds=data.interval_seconds,
                        notification_mode=data.notification_mode,
                        digest_interval_seconds=data.digest_interval_seconds,
                        enabled=True,
                    ),
                )
                searches_created += 1
                search_ids.append(search.id)
                existing_searches.append(search)
            except PlanLimitError as exc:
                limit_message = str(exc)
                break

        return PortalSubscribeResultRead(
            sources_created=sources_created,
            searches_created=searches_created,
            search_ids=search_ids,
            skipped_portal_ids=skipped,
            message=limit_message,
        )


def _resolve_presets(
    plan: PlanId,
    *,
    category: str | None,
    portal_ids: list[str] | None,
) -> list[PortalPreset]:
    if portal_ids:
        presets: list[PortalPreset] = []
        for portal_id in portal_ids:
            preset = get_portal_preset(portal_id)
            if preset is None:
                raise ValidationError(f"Unknown portal id '{portal_id}'")
            presets.append(preset)
    else:
        presets = list_portal_presets(category=category)  # type: ignore[arg-type]
    return [p for p in presets if scraper_allowed(plan, p.adapter_key)]


def _resolve_subscribe_presets(data: PortalSubscribeRequest, plan: PlanId) -> list[PortalPreset]:
    presets: list[PortalPreset] = []
    for portal_id in data.portal_ids:
        preset = get_portal_preset(portal_id)
        if preset is None:
            raise ValidationError(f"Unknown portal id '{portal_id}'")
        if not scraper_allowed(plan, preset.adapter_key):
            raise ValidationError(
                f"Portal '{preset.company_name}' requires a higher plan for its scraper."
            )
        presets.append(preset)
    return presets


def _build_filters(data: PortalSearchRequest | PortalSubscribeRequest) -> dict[str, Any]:
    filters: dict[str, Any] = {"keywords_include": data.keywords.strip()}
    if data.location and data.location.strip():
        filters["location"] = data.location.strip()
    if data.workplace:
        filters["workplace"] = data.workplace
    return filters


def _source_id_for_preset(preset: PortalPreset, owned: list[Source]) -> int | None:
    for source in owned:
        if PortalCatalogService._is_already_added(preset, [source]):
            return source.id
    return None


def _ensure_source(
    user_id: int,
    preset: PortalPreset,
    *,
    owned: list[Source],
    source_service: SourceService,
    limits: PlanLimitsService,
) -> tuple[Source, bool]:
    for source in owned:
        if PortalCatalogService._is_already_added(preset, [source]):
            return source, False
    limits.require_can_add_source(user_id, preset.adapter_key)
    source = source_service.create(
        user_id,
        SourceCreate(
            name=preset.company_name,
            adapter_key=preset.adapter_key,
            base_url=preset.base_url,
            default_config=dict(preset.default_config),
            enabled=True,
        ),
    )
    return source, True


def _has_matching_search(
    searches: list[Search],
    source_id: int,
    filters: dict[str, Any],
) -> bool:
    keywords = filters.get("keywords_include")
    for search in searches:
        if search.source_id != source_id:
            continue
        existing = search.filters.get("keywords_include") or search.filters.get("keywords")
        if existing == keywords:
            return True
    return False
