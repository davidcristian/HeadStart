"""Billing service unit tests."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.promo_code import PromoCode
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from app.services.billing import BillingService


@pytest.fixture
def billing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_unit")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_unit")
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_annual", "price_starter_annual")
    monkeypatch.setattr(settings, "stripe_price_plus_monthly", "price_plus_monthly")
    monkeypatch.setattr(settings, "stripe_price_plus_annual", "price_plus_annual")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_annual", "price_pro_annual")


def _add_user(db_session: Session, email: str = "billing-user@example.com") -> User:
    user = User(email=email, password_hash="hash", plan="free")
    return UserRepository(db_session).add(user)


def test_status_for_free_user(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    status = BillingService(db_session).status(user.id)
    assert status.configured is True
    assert status.plan == "free"
    assert status.can_checkout is True


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_create_checkout_creates_customer(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    user = _add_user(db_session)
    mock_customer_create.return_value = MagicMock(id="cus_new")
    mock_session_create.return_value = MagicMock(url="https://checkout.test/url")

    url = BillingService(db_session).create_checkout_session(
        user.id, plan="pro", billing_period="monthly"
    )
    assert url == "https://checkout.test/url"
    db_session.refresh(user)
    assert user.stripe_customer_id == "cus_new"


def test_plan_from_subscription_price_mapping(db_session: Session, billing_settings: None) -> None:
    service = BillingService(db_session)
    assert (
        service._plan_from_subscription(
            {
                "status": "active",
                "metadata": {},
                "items": {"data": [{"price": {"id": "price_starter_annual"}}]},
            },
            "active",
        )
        == "starter"
    )
    plan = service._plan_from_subscription(
        {
            "status": "active",
            "metadata": {},
            "items": {"data": [{"price": {"id": "price_pro_annual"}}]},
        },
        "active",
    )
    assert plan == "pro"


def test_unknown_subscription_price_defaults_to_lowest_paid_tier(
    db_session: Session, billing_settings: None
) -> None:
    """Regression: an unmappable price must not silently grant Pro for free."""
    service = BillingService(db_session)
    plan = service._plan_from_subscription(
        {
            "id": "sub_unknown",
            "status": "active",
            "metadata": {},
            "items": {"data": [{"price": {"id": "price_not_configured"}}]},
        },
        "active",
    )
    assert plan == "starter"


def test_subscription_without_items_falls_back_to_metadata_plan(
    db_session: Session, billing_settings: None
) -> None:
    service = BillingService(db_session)
    plan = service._plan_from_subscription(
        {"id": "sub_meta", "status": "active", "metadata": {"plan": "plus"}, "items": {"data": []}},
        "active",
    )
    assert plan == "plus"


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_plan_upgrade_promo_bills_target_plan_price(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    """A plan_upgrade promo must charge (and grant) the target plan, not the requested one."""
    user = _add_user(db_session)
    PromoCodeRepository(db_session).add(
        PromoCode(
            code="UPGRADE",
            promo_type="plan_upgrade",
            value_int=1,
            plan_target="pro",
            stripe_coupon_id="coupon_upgrade",
            stripe_promotion_code_id="promo_upgrade",
        )
    )
    mock_customer_create.return_value = MagicMock(id="cus_upgrade")
    mock_session_create.return_value = MagicMock(url="https://checkout.test/upgrade")

    BillingService(db_session).create_checkout_session(
        user.id, plan="starter", billing_period="monthly", promo_code="UPGRADE"
    )
    kwargs = mock_session_create.call_args.kwargs
    assert kwargs["line_items"] == [{"price": "price_pro_monthly", "quantity": 1}]
    assert kwargs["metadata"]["plan"] == "pro"
    assert kwargs["subscription_data"]["metadata"]["plan"] == "pro"
    assert kwargs["discounts"] == [{"promotion_code": "promo_upgrade"}]
