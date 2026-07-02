"""Plan limit and feature schemas."""

from typing import Literal

from pydantic import BaseModel

PlanId = Literal["free", "starter", "plus", "pro"]


class PlanLimitsRead(BaseModel):
    max_searches: int
    max_sources: int
    max_targets: int


class PlanUsageRead(BaseModel):
    searches: int
    sources: int
    targets: int


class PlanFeaturesRead(BaseModel):
    digest_mode: bool
    ai_summaries: bool
    site_credentials: bool
    rss_feed: bool


class AccountPlanRead(BaseModel):
    """Effective plan caps, usage, and allowed adapters for the signed-in user."""

    plan: PlanId
    effective_plan: PlanId
    unlimited: bool
    show_ads: bool
    limits: PlanLimitsRead
    usage: PlanUsageRead
    features: PlanFeaturesRead
    allowed_scrapers: list[str]
    allowed_notifiers: list[str]
