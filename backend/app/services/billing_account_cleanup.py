"""Best-effort Stripe teardown when a local account is deleted."""

from __future__ import annotations

import logging

import stripe

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def release_stripe_billing(user: User) -> None:
    """Cancel the subscription and delete the Stripe customer if present.

    Stripe failures are logged and swallowed so local GDPR deletion still
    completes when the billing provider is unreachable or already cleaned up.
    """
    if not settings.stripe_secret_key:
        return
    stripe.api_key = settings.stripe_secret_key
    subscription_id = user.stripe_subscription_id
    customer_id = user.stripe_customer_id
    if subscription_id:
        _cancel_subscription(subscription_id, user_id=user.id)
    if customer_id:
        _delete_customer(customer_id, user_id=user.id)


def _cancel_subscription(subscription_id: str, *, user_id: int) -> None:
    try:
        stripe.Subscription.cancel(subscription_id)
        logger.info(
            "canceled Stripe subscription %s for deleted user %s",
            subscription_id,
            user_id,
        )
    except stripe.InvalidRequestError as exc:
        # Already canceled / missing is fine; other invalid requests still log.
        logger.warning(
            "Stripe subscription cancel for user %s (%s): %s",
            user_id,
            subscription_id,
            exc,
        )
    except stripe.StripeError as exc:
        logger.warning(
            "Stripe subscription cancel failed for user %s (%s): %s",
            user_id,
            subscription_id,
            exc,
        )


def _delete_customer(customer_id: str, *, user_id: int) -> None:
    try:
        stripe.Customer.delete(customer_id)
        logger.info(
            "deleted Stripe customer %s for deleted user %s",
            customer_id,
            user_id,
        )
    except stripe.InvalidRequestError as exc:
        logger.warning(
            "Stripe customer delete for user %s (%s): %s",
            user_id,
            customer_id,
            exc,
        )
    except stripe.StripeError as exc:
        logger.warning(
            "Stripe customer delete failed for user %s (%s): %s",
            user_id,
            customer_id,
            exc,
        )
