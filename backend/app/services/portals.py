"""Curated portal catalog business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.appliers import has_applier
from app.core.plans import scraper_allowed
from app.models.source import Source
from app.models.user import User
from app.portals.catalog import PortalCategory, PortalPreset, list_portal_presets
from app.repositories.sources import SourceRepository
from app.schemas.portal import PortalListRead, PortalRead
from app.services.plan_limits import PlanLimitsService


class PortalCatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = SourceRepository(session)
        self.limits = PlanLimitsService(session)

    def list_for_user(
        self,
        user: User,
        *,
        category: PortalCategory | None = None,
        query: str | None = None,
    ) -> PortalListRead:
        """Return curated portals annotated with plan and duplicate status."""
        plan = self.limits.resolve_plan(user)
        owned = self.sources.list_all(user.id)
        presets = list_portal_presets(category=category, query=query)
        items = [
            self._to_read(
                preset,
                plan=plan,
                owned=owned,
            )
            for preset in presets
        ]
        categories: list[PortalCategory] = ["big_tech", "unicorn", "ai"]
        return PortalListRead(items=items, categories=categories)

    def _to_read(self, preset: PortalPreset, *, plan: str, owned: list[Source]) -> PortalRead:
        return PortalRead(
            id=preset.id,
            company_name=preset.company_name,
            category=preset.category,
            adapter_key=preset.adapter_key,
            base_url=preset.base_url,
            default_config=dict(preset.default_config),
            supports_auto_apply=has_applier(preset.adapter_key),
            allowed_on_plan=scraper_allowed(plan, preset.adapter_key),  # type: ignore[arg-type]
            already_added=self._is_already_added(preset, owned),
        )

    @staticmethod
    def _is_already_added(preset: PortalPreset, owned: list[Source]) -> bool:
        """Detect whether the user already has an equivalent source."""
        portal_id = preset.default_config.get("portal_id")
        for source in owned:
            if source.default_config.get("portal_id") == portal_id:
                return True
            if _normalize_url(source.base_url) == _normalize_url(preset.base_url):
                return True
            if _config_keys_match(preset, source):
                return True
        return False


def _normalize_url(url: str) -> str:
    return url.rstrip("/").casefold()


def _config_keys_match(preset: PortalPreset, source: Source) -> bool:
    """Match adapter-specific identity fields when portal_id was not stored."""
    if source.adapter_key != preset.adapter_key:
        return False
    cfg = source.default_config
    pcfg = preset.default_config
    if preset.adapter_key == "greenhouse":
        return cfg.get("board_token") == pcfg.get("board_token")
    if preset.adapter_key == "lever":
        return cfg.get("site") == pcfg.get("site")
    if preset.adapter_key == "ashby":
        return cfg.get("board") == pcfg.get("board")
    if preset.adapter_key == "workday":
        return cfg.get("tenant") == pcfg.get("tenant") and cfg.get("site") == pcfg.get("site")
    if preset.adapter_key == "google_careers":
        return cfg.get("portal_id") == pcfg.get("portal_id")
    return False
