"""Apply Stripe subscription.created/updated/deleted events to local users."""

from __future__ import annotations

import logging
from typing import Any

from app.core.billing_prices import plan_for_price_id, subscription_grants_plan
from app.core.plans import VALID_PLANS, PlanId
from app.models.user import User
from app.repositories.users import UserRepository

logger = logging.getLogger(__name__)

# Fallback for an active subscription whose price/metadata can't be mapped.
_UNRESOLVED_PLAN: PlanId = "starter"


def apply_subscription_updated(
    users: UserRepository,
    subscription: dict[str, Any],
    *,
    event_at: int | None = None,
) -> None:
    """Upsert plan/status from a subscription created/updated webhook."""
    user = user_for_subscription(users, subscription)
    if user is None:
        logger.warning("subscription update for unknown customer %s", subscription.get("customer"))
        return
    sub_id = subscription.get("id")
    sub_id_str = str(sub_id) if isinstance(sub_id, str) and sub_id else None
    if not should_apply_subscription_event(user, sub_id_str, event_at=event_at):
        logger.info(
            "ignoring stale/superseded subscription update %s for user %s",
            sub_id_str,
            user.id,
        )
        return
    status = str(subscription.get("status") or "")
    plan = plan_from_subscription(subscription, status)
    updates: dict[str, Any] = {
        "stripe_subscription_id": sub_id_str or user.stripe_subscription_id,
        "subscription_status": status or None,
        "plan": plan,
    }
    if event_at is not None:
        updates["stripe_billing_event_at"] = event_at
    users.update_billing(user, **updates)


def apply_subscription_deleted(
    users: UserRepository,
    subscription: dict[str, Any],
    *,
    event_at: int | None = None,
) -> None:
    """Downgrade when the user's current subscription is deleted."""
    user = user_for_subscription(users, subscription)
    if user is None:
        return
    sub_id = subscription.get("id")
    sub_id_str = str(sub_id) if isinstance(sub_id, str) and sub_id else None
    # Deleted must target the user's current subscription; never wipe a newer one.
    if user.stripe_subscription_id is None or sub_id_str != user.stripe_subscription_id:
        logger.info(
            "ignoring subscription.deleted for %s (current=%s) user %s",
            sub_id_str,
            user.stripe_subscription_id,
            user.id,
        )
        return
    if is_stale_billing_event(user, event_at):
        logger.info(
            "ignoring stale subscription.deleted %s for user %s",
            sub_id_str,
            user.id,
        )
        return
    updates: dict[str, Any] = {
        "stripe_subscription_id": None,
        "subscription_status": "canceled",
        "plan": "free",
    }
    if event_at is not None:
        updates["stripe_billing_event_at"] = event_at
    users.update_billing(user, **updates)


def should_apply_subscription_event(
    user: User,
    subscription_id: str | None,
    *,
    event_at: int | None,
) -> bool:
    """Reject superseded subscription ids and out-of-order lifecycle events."""
    if is_stale_billing_event(user, event_at):
        return False
    current = user.stripe_subscription_id
    return not (current and subscription_id and subscription_id != current)


def is_stale_billing_event(user: User, event_at: int | None) -> bool:
    """True when event_at is older than the last applied subscription lifecycle event."""
    watermark = user.stripe_billing_event_at
    if watermark is None:
        return False
    # Once a watermark exists, unsigned events cannot prove they are fresh.
    if event_at is None:
        return True
    return event_at < watermark


def plan_from_subscription(subscription: dict[str, Any], status: str) -> PlanId:
    """Resolve the local plan id from a Stripe subscription payload."""
    if not subscription_grants_plan(status):
        return "free"
    items = subscription.get("items", {}).get("data", [])
    if items:
        price = items[0].get("price", {})
        price_id = price.get("id")
        if isinstance(price_id, str):
            resolved = plan_for_price_id(price_id)
            if resolved:
                return resolved
    metadata_plan = subscription.get("metadata", {}).get("plan")
    if isinstance(metadata_plan, str) and metadata_plan in VALID_PLANS:
        return metadata_plan  # type: ignore[return-value]
    logger.warning(
        "subscription %s grants a plan but price/metadata is unrecognized; defaulting to %s",
        subscription.get("id"),
        _UNRESOLVED_PLAN,
    )
    return _UNRESOLVED_PLAN


def user_for_subscription(users: UserRepository, subscription: dict[str, Any]) -> User | None:
    """Resolve the owning user from subscription metadata or customer id."""
    metadata = subscription.get("metadata") or {}
    user_id = metadata.get("user_id")
    if user_id is not None:
        try:
            user = users.get(int(user_id))
            if user:
                return user
        except (TypeError, ValueError):
            pass
    customer_id = subscription.get("customer")
    if isinstance(customer_id, str):
        return users.get_by_stripe_customer_id(customer_id)
    return None
