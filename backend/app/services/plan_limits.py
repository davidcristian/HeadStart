"""Per-plan resource caps and feature gates."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

from sqlalchemy.orm import Session

from app.core.exceptions import PlanLimitError
from app.core.plans import (
    DEFAULT_PLAN,
    VALID_PLANS,
    PlanFeatures,
    PlanId,
    notifier_allowed,
    plan_display_name,
    plan_features_for,
    plan_limits_for,
    required_plan_phrase,
    scraper_allowed,
)
from app.models.base import utcnow
from app.models.user import User
from app.notifiers import available_notifiers
from app.repositories.application_logs import ApplicationLogRepository
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.repositories.users import UserRepository
from app.scrapers import available_scrapers
from app.services.plan_limit_checks import (
    require_notifier,
    require_scraper,
    require_under_cap,
)


class PlanLimitsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sources = SourceRepository(session)
        self.searches = SearchRepository(session)
        self.targets = TargetRepository(session)
        self.application_logs = ApplicationLogRepository(session)

    def resolve_plan(self, user: User) -> PlanId:
        """Effective plan for limits (admins map to Pro caps for display)."""
        if user.is_admin:
            return "pro"
        if user.plan in VALID_PLANS:
            return cast(PlanId, user.plan)
        return DEFAULT_PLAN

    def usage(self, user_id: int) -> dict[str, int]:
        """Current owned resource counts."""
        since = utcnow() - timedelta(days=1)
        return {
            "searches": len(self.searches.list_all(user_id)),
            "sources": len(self.sources.list_all(user_id)),
            "targets": len(self.targets.list_all(user_id)),
            "auto_applies_last_day": self.application_logs.count_live_since(user_id, since=since),
        }

    def show_ads_for(self, user: User) -> bool:
        """Whether the signed-in user should see in-app ads (free tier only)."""
        if user.is_admin:
            return False
        return self.resolve_plan(user) == "free"

    def snapshot(self, user: User) -> dict[str, object]:
        """Plan, limits, usage, features, and allowed adapters for the UI."""
        plan = self.resolve_plan(user)
        limits = plan_limits_for(plan)
        features = plan_features_for(plan)
        usage = self.usage(user.id)
        return {
            "plan": user.plan,
            "effective_plan": plan,
            "unlimited": user.is_admin,
            "show_ads": self.show_ads_for(user),
            "limits": {
                "max_searches": limits.max_searches,
                "max_sources": limits.max_sources,
                "max_targets": limits.max_targets,
                "max_auto_applies_per_day": limits.max_auto_applies_per_day,
            },
            "usage": usage,
            "features": {
                "digest_mode": features.digest_mode,
                "ai_summaries": features.ai_summaries,
                "site_credentials": features.site_credentials,
                "rss_feed": features.rss_feed,
                "portal_search": features.portal_search,
            },
            "allowed_scrapers": self.allowed_scrapers(plan),
            "allowed_notifiers": self.allowed_notifiers(plan),
        }

    def allowed_scrapers(self, plan: PlanId) -> list[str]:
        """Scraper keys the plan may use."""
        return sorted(key for key in available_scrapers() if scraper_allowed(plan, key))

    def allowed_notifiers(self, plan: PlanId) -> list[str]:
        """Notifier types the plan may use."""
        return sorted(key for key in available_notifiers() if notifier_allowed(plan, key))

    def features_for(self, user: User) -> PlanFeatures:
        """Feature flags for the user's effective plan."""
        return plan_features_for(self.resolve_plan(user))

    def allows_summaries(self, user_id: int) -> bool:
        """Whether AI/heuristic summaries may run for this user."""
        user = self.users.get(user_id)
        if user is None:
            return False
        return user.is_admin or plan_features_for(self.resolve_plan(user)).ai_summaries

    def allows_scraper(self, user_id: int, adapter_key: str) -> bool:
        """Whether this scraper may run for the user at consumption time."""
        user = self.users.get(user_id)
        if user is None:
            return False
        return user.is_admin or scraper_allowed(self.resolve_plan(user), adapter_key)

    def allows_notifier(self, user_id: int, target_type: str) -> bool:
        """Whether this notifier may deliver for the user at consumption time."""
        user = self.users.get(user_id)
        if user is None:
            return False
        return user.is_admin or notifier_allowed(self.resolve_plan(user), target_type)

    def allows_pipeline_auto_apply(self, user_id: int) -> bool:
        """Whether another live pipeline auto-apply may be queued under the daily cap."""
        user = self.users.get(user_id)
        if user is None:
            return False
        if user.is_admin:
            return True
        plan = self.resolve_plan(user)
        maximum = plan_limits_for(plan).max_auto_applies_per_day
        if maximum <= 0:
            return True
        since = utcnow() - timedelta(days=1)
        return self.application_logs.count_live_since(user_id, since=since) < maximum

    def require_can_add_source(self, user_id: int, adapter_key: str) -> None:
        """Raise when the user cannot create another source or use this adapter."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        require_scraper(plan, adapter_key)
        require_under_cap(
            plan,
            code="source_limit",
            resource="sources",
            current=len(self.sources.list_all(user_id)),
            maximum=plan_limits_for(plan).max_sources,
        )

    def require_can_update_source_adapter(self, user_id: int, adapter_key: str) -> None:
        """Raise when switching a source to a disallowed adapter."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        require_scraper(self.resolve_plan(user), adapter_key)

    def require_can_add_search(self, user_id: int) -> None:
        """Raise when the user cannot create another search."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        require_under_cap(
            plan,
            code="search_limit",
            resource="searches",
            current=len(self.searches.list_all(user_id)),
            maximum=plan_limits_for(plan).max_searches,
        )

    def require_digest_mode(self, user_id: int) -> None:
        """Raise when digest notifications are not on the user's plan."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        if not plan_features_for(plan).digest_mode:
            raise PlanLimitError(
                f"Digest notifications require a {required_plan_phrase('starter')} plan "
                f"(you are on {plan_display_name(plan)}).",
                code="digest_mode",
                plan=plan,
            )

    def require_can_add_target(self, user_id: int, target_type: str) -> None:
        """Raise when the user cannot create another target or use this type."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        require_notifier(plan, target_type)
        require_under_cap(
            plan,
            code="target_limit",
            resource="notification targets",
            current=len(self.targets.list_all(user_id)),
            maximum=plan_limits_for(plan).max_targets,
        )

    def require_can_update_target_type(self, user_id: int, target_type: str) -> None:
        """Raise when switching a target to a disallowed notifier type."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        require_notifier(self.resolve_plan(user), target_type)

    def require_site_credentials(self, user_id: int) -> None:
        """Raise when encrypted site credentials are not on the user's plan."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        if not plan_features_for(plan).site_credentials:
            raise PlanLimitError(
                f"Site credentials require a {required_plan_phrase('plus')} plan "
                f"(you are on {plan_display_name(plan)}).",
                code="site_credentials",
                plan=plan,
            )

    def require_rss_feed(self, user: User) -> None:
        """Raise when RSS export is not on the user's plan."""
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        if not plan_features_for(plan).rss_feed:
            raise PlanLimitError(
                f"RSS export requires a {required_plan_phrase('pro')} plan "
                f"(you are on {plan_display_name(plan)}).",
                code="rss_feed",
                plan=plan,
            )

    def require_portal_search(self, user: User) -> None:
        """Raise when cross-portal search is not on the user's plan."""
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        if not plan_features_for(plan).portal_search:
            raise PlanLimitError(
                f"Curated portal search requires a {required_plan_phrase('pro')} plan "
                f"(you are on {plan_display_name(plan)}).",
                code="portal_search",
                plan=plan,
            )

    def _require_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise PlanLimitError("User not found.", code="user_not_found", plan=DEFAULT_PLAN)
        return user
