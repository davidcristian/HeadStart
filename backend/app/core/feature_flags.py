"""Helpers for Settings-derived feature flags."""

from typing import Protocol


class _StripeSettings(Protocol):
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_starter_monthly: str
    stripe_price_starter_annual: str
    stripe_price_plus_monthly: str
    stripe_price_plus_annual: str
    stripe_price_pro_monthly: str
    stripe_price_pro_annual: str


def stripe_billing_configured(settings: _StripeSettings) -> bool:
    """True when Stripe keys and all paid-tier price IDs are set."""
    return bool(
        settings.stripe_secret_key
        and settings.stripe_webhook_secret
        and settings.stripe_price_starter_monthly
        and settings.stripe_price_starter_annual
        and settings.stripe_price_plus_monthly
        and settings.stripe_price_plus_annual
        and settings.stripe_price_pro_monthly
        and settings.stripe_price_pro_annual
    )
