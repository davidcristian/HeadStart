"""Stripe price ID mapping tests."""

import pytest

from app.core.billing_prices import plan_for_price_id, price_id_for
from app.core.config import settings


@pytest.fixture
def billing_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_annual", "price_starter_annual")
    monkeypatch.setattr(settings, "stripe_price_plus_monthly", "price_plus_monthly")
    monkeypatch.setattr(settings, "stripe_price_plus_annual", "price_plus_annual")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_annual", "price_pro_annual")


def test_price_id_for_all_paid_plans(billing_prices: None) -> None:
    assert price_id_for("starter", "monthly") == "price_starter_monthly"
    assert price_id_for("starter", "annual") == "price_starter_annual"
    assert price_id_for("plus", "monthly") == "price_plus_monthly"
    assert price_id_for("plus", "annual") == "price_plus_annual"
    assert price_id_for("pro", "monthly") == "price_pro_monthly"
    assert price_id_for("pro", "annual") == "price_pro_annual"


def test_plan_for_price_id_round_trip(billing_prices: None) -> None:
    assert plan_for_price_id("price_starter_monthly") == "starter"
    assert plan_for_price_id("price_plus_annual") == "plus"
    assert plan_for_price_id("price_pro_monthly") == "pro"
    assert plan_for_price_id("price_unknown") is None
