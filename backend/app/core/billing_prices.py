"""Map Stripe price IDs to subscription plans."""

from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.core.plans import PlanId

BillingPeriod = Literal["monthly", "annual"]

_ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing", "past_due"})


def price_id_for(plan: Literal["pro"], period: BillingPeriod) -> str:
    """Return the configured Stripe price ID for a self-serve plan."""
    if plan == "pro":
        if period == "monthly":
            return settings.stripe_price_pro_monthly
        return settings.stripe_price_pro_annual
    raise ValueError(f"Unsupported checkout plan: {plan}")


def plan_for_price_id(price_id: str) -> PlanId | None:
    """Resolve a Stripe price ID to a plan, if it matches a configured price."""
    if price_id in (settings.stripe_price_pro_monthly, settings.stripe_price_pro_annual):
        return "pro"
    return None


def subscription_grants_plan(status: str) -> bool:
    """Whether a Stripe subscription status should keep the paid plan active."""
    return status in _ACTIVE_SUBSCRIPTION_STATUSES
