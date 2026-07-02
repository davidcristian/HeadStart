"""Subscription plan definitions: caps and feature gates.

Mirrors the public pricing page (`frontend/src/lib/pricing.ts`). Stripe webhooks
and the admin panel update ``user.plan``; new accounts start on ``free``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlanId = Literal["free", "pro", "team"]

# Scrapers included on Free (common ATS + generic HTML). Pro unlocks the rest.
FREE_SCRAPERS: frozenset[str] = frozenset(
    {
        "greenhouse",
        "lever",
        "ashby",
        "generic_html",
        "workday",
        "amazon_jobs",
        "google_careers",
        "microsoft_careers",
    }
)
PREMIUM_SCRAPERS: frozenset[str] = frozenset({"indeed", "linkedin", "playwright"})

# Outbound webhooks are Pro+; other notifiers are available on Free.
PREMIUM_NOTIFIERS: frozenset[str] = frozenset({"webhook"})

DEFAULT_PLAN: PlanId = "free"
VALID_PLANS: frozenset[str] = frozenset({"free", "pro", "team"})


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
    "pro": PlanLimits(max_searches=15, max_sources=15, max_targets=5),
    "team": PlanLimits(max_searches=50, max_sources=50, max_targets=20),
}

_PLAN_FEATURES: dict[PlanId, PlanFeatures] = {
    "free": PlanFeatures(
        digest_mode=False,
        ai_summaries=False,
        site_credentials=False,
        rss_feed=False,
        portal_search=False,
    ),
    "pro": PlanFeatures(
        digest_mode=True,
        ai_summaries=True,
        site_credentials=True,
        rss_feed=True,
        portal_search=True,
    ),
    "team": PlanFeatures(
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
        return plan in ("pro", "team")
    # Unknown adapters default to allowed so new scrapers are not accidentally blocked.
    return True


def notifier_allowed(plan: PlanId, notifier_type: str) -> bool:
    """Whether a notifier type is available on the given plan."""
    if notifier_type in PREMIUM_NOTIFIERS:
        return plan in ("pro", "team")
    return True


def plan_display_name(plan: PlanId) -> str:
    """Human label for error messages."""
    return {"free": "Free", "pro": "Pro", "team": "Team"}[plan]
