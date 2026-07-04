"""Shared PlanLimitError raisers for cap and adapter gates."""

from __future__ import annotations

from app.core.exceptions import PlanLimitError
from app.core.plans import (
    PlanId,
    notifier_allowed,
    plan_display_name,
    required_plan_phrase,
    scraper_allowed,
)


def require_under_cap(
    plan: PlanId,
    *,
    code: str,
    resource: str,
    current: int,
    maximum: int,
) -> None:
    """Raise when ``current`` is already at or above ``maximum``."""
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


def require_scraper(plan: PlanId, adapter_key: str) -> None:
    """Raise when the scraper adapter is not on the plan."""
    if scraper_allowed(plan, adapter_key):
        return
    label = plan_display_name(plan)
    raise PlanLimitError(
        f"The '{adapter_key}' scraper requires a {required_plan_phrase('plus')} plan "
        f"(you are on {label}).",
        code="premium_scraper",
        plan=plan,
    )


def require_notifier(plan: PlanId, target_type: str) -> None:
    """Raise when the notifier type is not on the plan."""
    if notifier_allowed(plan, target_type):
        return
    label = plan_display_name(plan)
    raise PlanLimitError(
        f"The '{target_type}' notifier requires a {required_plan_phrase('pro')} plan "
        f"(you are on {label}).",
        code="premium_notifier",
        plan=plan,
    )
