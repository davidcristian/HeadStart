"""Per-plan resource caps and feature gates."""

from __future__ import annotations

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
    scraper_allowed,
)
from app.models.user import User
from app.notifiers import available_notifiers
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.repositories.users import UserRepository
from app.scrapers import available_scrapers


class PlanLimitsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sources = SourceRepository(session)
        self.searches = SearchRepository(session)
        self.targets = TargetRepository(session)

    def resolve_plan(self, user: User) -> PlanId:
        """Effective plan for limits (admins map to Pro caps for display)."""
        if user.is_admin:
            return "pro"
        if user.plan in VALID_PLANS:
            return cast(PlanId, user.plan)
        return DEFAULT_PLAN

    def usage(self, user_id: int) -> dict[str, int]:
        """Current owned resource counts."""
        return {
            "searches": len(self.searches.list_all(user_id)),
            "sources": len(self.sources.list_all(user_id)),
            "targets": len(self.targets.list_all(user_id)),
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
            "plan": user.plan if not user.is_admin else user.plan,
            "effective_plan": plan,
            "unlimited": user.is_admin,
            "show_ads": self.show_ads_for(user),
            "limits": {
                "max_searches": limits.max_searches,
                "max_sources": limits.max_sources,
                "max_targets": limits.max_targets,
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
        if user.is_admin:
            return True
        return plan_features_for(self.resolve_plan(user)).ai_summaries

    def require_can_add_source(self, user_id: int, adapter_key: str) -> None:
        """Raise when the user cannot create another source or use this adapter."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        self._require_scraper(plan, adapter_key)
        self._require_under_cap(
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
        self._require_scraper(self.resolve_plan(user), adapter_key)

    def require_can_add_search(self, user_id: int) -> None:
        """Raise when the user cannot create another search."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        self._require_under_cap(
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
                "Digest notifications require a Pro plan "
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
        self._require_notifier(plan, target_type)
        self._require_under_cap(
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
        self._require_notifier(self.resolve_plan(user), target_type)

    def require_site_credentials(self, user_id: int) -> None:
        """Raise when encrypted site credentials are not on the user's plan."""
        user = self._require_user(user_id)
        if user.is_admin:
            return
        plan = self.resolve_plan(user)
        if not plan_features_for(plan).site_credentials:
            raise PlanLimitError(
                "Site credentials require a Pro plan " f"(you are on {plan_display_name(plan)}).",
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
                f"RSS export requires a Pro plan (you are on {plan_display_name(plan)}).",
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
                "Curated portal search requires a Pro plan "
                f"(you are on {plan_display_name(plan)}).",
                code="portal_search",
                plan=plan,
            )

    def _require_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise PlanLimitError("User not found.", code="user_not_found", plan=DEFAULT_PLAN)
        return user

    @staticmethod
    def _require_under_cap(
        plan: PlanId,
        *,
        code: str,
        resource: str,
        current: int,
        maximum: int,
    ) -> None:
        if current < maximum:
            return
        label = plan_display_name(plan)
        raise PlanLimitError(
            f"{label} plan allows up to {maximum} {resource}. "
            "Upgrade your plan or remove an existing one to add more.",
            code=code,
            plan=plan,
            limit=maximum,
        )

    @staticmethod
    def _require_scraper(plan: PlanId, adapter_key: str) -> None:
        if scraper_allowed(plan, adapter_key):
            return
        label = plan_display_name(plan)
        raise PlanLimitError(
            f"The '{adapter_key}' scraper requires a Pro plan (you are on {label}).",
            code="premium_scraper",
            plan=plan,
        )

    @staticmethod
    def _require_notifier(plan: PlanId, target_type: str) -> None:
        if notifier_allowed(plan, target_type):
            return
        label = plan_display_name(plan)
        raise PlanLimitError(
            f"The '{target_type}' notifier requires a Pro plan (you are on {label}).",
            code="premium_notifier",
            plan=plan,
        )
