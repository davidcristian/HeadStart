"""Subscription plan definitions: caps and feature gates.

Mirrors the public pricing page (`frontend/src/lib/pricing.ts`). Stripe webhooks
and the admin panel update ``user.plan``; new accounts start on ``free``.

See docs/adr/0010-four-tier-pricing.md for the tier ladder and feature matrix.
Feature enforcement for Starter / Plus / Pro is refined in Phase 14b.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlanId = Literal["free", "starter", "plus", "pro"]

# Scrapers included on Free (common ATS + generic HTML). Pro unlocks the rest.
FREE_SCRAPERS: frozenset[str] = frozenset(
    {
        "greenhouse",
        "lever",
        "ashby",
        "generic_html",
        "workday",
        "amazon_jobs",
        "apple_careers",
        "google_careers",
        "meta_careers",
        "microsoft_careers",
    }
)
PREMIUM_SCRAPERS: frozenset[str] = frozenset({"indeed", "linkedin", "playwright"})

# Outbound webhooks are Pro+; other notifiers are available on Free.
PREMIUM_NOTIFIERS: frozenset[str] = frozenset({"webhook"})

DEFAULT_PLAN: PlanId = "free"
VALID_PLANS: frozenset[str] = frozenset({"free", "starter", "plus", "pro"})


@dataclass(frozen=True, slots=True)
class PlanLimits:
    max_searches: int
    max_sources: int
    max_targets: int


@dataclass(frozen=True, slots=True)
class PlanFeatures:
    digest_mode: bool
    ai_summaries: bool
    site_credentials: bool
    rss_feed: bool
    portal_search: bool


_PLAN_LIMITS: dict[PlanId, PlanLimits] = {
    "free": PlanLimits(max_searches=3, max_sources=3, max_targets=1),
    "starter": PlanLimits(max_searches=5, max_sources=5, max_targets=2),
    "plus": PlanLimits(max_searches=10, max_sources=10, max_targets=3),
    "pro": PlanLimits(max_searches=20, max_sources=20, max_targets=5),
}

# Transitional feature flags for 14a — Phase 14b aligns gates with the ADR matrix.
_PLAN_FEATURES: dict[PlanId, PlanFeatures] = {
    "free": PlanFeatures(
        digest_mode=False,
        ai_summaries=False,
        site_credentials=False,
        rss_feed=False,
        portal_search=False,
    ),
    "starter": PlanFeatures(
        digest_mode=False,
        ai_summaries=False,
        site_credentials=False,
        rss_feed=False,
        portal_search=False,
    ),
    "plus": PlanFeatures(
        digest_mode=True,
        ai_summaries=True,
        site_credentials=True,
        rss_feed=True,
        portal_search=True,
    ),
    "pro": PlanFeatures(
        digest_mode=True,
        ai_summaries=True,
        site_credentials=True,
        rss_feed=True,
        portal_search=True,
    ),
}


def plan_limits_for(plan: PlanId) -> PlanLimits:
    """Return numeric caps for a plan."""
    return _PLAN_LIMITS[plan]


def plan_features_for(plan: PlanId) -> PlanFeatures:
    """Return feature gates for a plan."""
    return _PLAN_FEATURES[plan]


def scraper_allowed(plan: PlanId, adapter_key: str) -> bool:
    """Whether a scraper adapter is available on the given plan."""
    if adapter_key in FREE_SCRAPERS:
        return True
    if adapter_key in PREMIUM_SCRAPERS:
        return plan == "pro"
    # Unknown adapters default to allowed so new scrapers are not accidentally blocked.
    return True


def notifier_allowed(plan: PlanId, notifier_type: str) -> bool:
    """Whether a notifier type is available on the given plan."""
    if notifier_type in PREMIUM_NOTIFIERS:
        return plan == "pro"
    return True


def plan_display_name(plan: PlanId) -> str:
    """Human label for error messages."""
    return {
        "free": "Free",
        "starter": "Starter",
        "plus": "Plus",
        "pro": "Pro",
    }[plan]
