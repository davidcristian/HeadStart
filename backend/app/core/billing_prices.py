"""Map Stripe price IDs to subscription plans."""

from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.core.plans import PlanId

BillingPeriod = Literal["monthly", "annual"]
CheckoutPlanId = Literal["starter", "plus", "pro"]

_ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing", "past_due"})


def _price_pairs() -> list[tuple[str, CheckoutPlanId, BillingPeriod]]:
    """Configured Stripe price IDs with their plan and billing period."""
    return [
        (settings.stripe_price_starter_monthly, "starter", "monthly"),
        (settings.stripe_price_starter_annual, "starter", "annual"),
        (settings.stripe_price_plus_monthly, "plus", "monthly"),
        (settings.stripe_price_plus_annual, "plus", "annual"),
        (settings.stripe_price_pro_monthly, "pro", "monthly"),
        (settings.stripe_price_pro_annual, "pro", "annual"),
    ]


def price_id_for(plan: CheckoutPlanId, period: BillingPeriod) -> str:
    """Return the configured Stripe price ID for a self-serve plan."""
    for price_id, mapped_plan, mapped_period in _price_pairs():
        if mapped_plan == plan and mapped_period == period:
            return price_id
    raise ValueError(f"Unsupported checkout plan: {plan}")


def plan_for_price_id(price_id: str) -> PlanId | None:
    """Resolve a Stripe price ID to a plan, if it matches a configured price."""
    for configured_id, plan, _period in _price_pairs():
        if price_id == configured_id:
            return plan
    return None


def subscription_grants_plan(status: str) -> bool:
    """Whether a Stripe subscription status should keep the paid plan active."""
    return status in _ACTIVE_SUBSCRIPTION_STATUSES
