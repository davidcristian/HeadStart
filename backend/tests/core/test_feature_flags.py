"""Unit tests for Settings-derived feature flags."""

from types import SimpleNamespace

from app.core.feature_flags import stripe_billing_configured


def test_stripe_billing_configured_requires_all_fields() -> None:
    base = {
        "stripe_secret_key": "sk",
        "stripe_webhook_secret": "whsec",
        "stripe_price_starter_monthly": "p1",
        "stripe_price_starter_annual": "p2",
        "stripe_price_plus_monthly": "p3",
        "stripe_price_plus_annual": "p4",
        "stripe_price_pro_monthly": "p5",
        "stripe_price_pro_annual": "p6",
    }
    assert stripe_billing_configured(SimpleNamespace(**base)) is True
    missing = dict(base)
    missing["stripe_price_pro_annual"] = ""
    assert stripe_billing_configured(SimpleNamespace(**missing)) is False
