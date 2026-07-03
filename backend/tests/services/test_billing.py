"""Billing service unit tests."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
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


# --- status / plan mapping ------------------------------------------------


def test_status_with_active_subscription_cannot_checkout(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_x",
        stripe_subscription_id="sub_x",
        subscription_status="active",
        plan="pro",
    )
    status = BillingService(db_session).status(user.id)
    assert status.can_checkout is False
    assert status.can_manage is True
    assert status.has_stripe_subscription is True


def test_plan_id_falls_back_to_free_for_unknown(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    user.plan = "legacy"
    db_session.flush()
    status = BillingService(db_session).status(user.id)
    assert status.plan == "free"


def test_status_missing_user_raises(db_session: Session, billing_settings: None) -> None:
    with pytest.raises(NotFoundError):
        BillingService(db_session).status(999999)


# --- checkout guards ------------------------------------------------------


def test_checkout_requires_billing_enabled(db_session: Session) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not configured"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="pro", billing_period="monthly"
        )


def test_checkout_rejects_invalid_plan(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="Invalid checkout plan"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="ultra", billing_period="monthly"
        )


def test_checkout_rejects_when_already_subscribed(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, subscription_status="active")
    with pytest.raises(ValidationError, match="already have an active subscription"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="pro", billing_period="monthly"
        )


def test_checkout_unsupported_period_raises(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not fully configured"):
        BillingService(db_session).create_checkout_session(
            user.id,
            plan="pro",
            billing_period="weekly",  # type: ignore[arg-type]
        )


@patch("app.services.billing.price_id_for", return_value="")
def test_checkout_missing_price_raises(
    _mock_price: MagicMock, db_session: Session, billing_settings: None
) -> None:
    # billing_enabled requires every price to be set, so an empty resolved price
    # is only reachable by forcing price_id_for to return "".
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not fully configured"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="pro", billing_period="monthly"
        )


@patch("app.services.billing.stripe.checkout.Session.create")
def test_checkout_free_trial_promo_sets_trial(
    mock_session_create: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_trial")
    PromoCodeRepository(db_session).add(
        PromoCode(code="FREE30", promo_type="free_trial_days", value_int=30)
    )
    mock_session_create.return_value = MagicMock(url="https://checkout.test/trial")

    BillingService(db_session).create_checkout_session(
        user.id, plan="starter", billing_period="monthly", promo_code="FREE30"
    )
    kwargs = mock_session_create.call_args.kwargs
    assert kwargs["subscription_data"]["trial_period_days"] == 30
    assert "discounts" not in kwargs


@patch("app.services.billing.stripe.checkout.Session.create")
def test_checkout_raises_when_stripe_returns_no_url(
    mock_session_create: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_nourl")
    mock_session_create.return_value = MagicMock(url=None)
    with pytest.raises(ValidationError, match="did not return a checkout URL"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="starter", billing_period="monthly"
        )


def test_create_checkout_missing_user_raises(db_session: Session, billing_settings: None) -> None:
    with pytest.raises(NotFoundError):
        BillingService(db_session).create_checkout_session(
            999999, plan="pro", billing_period="monthly"
        )


# --- portal ---------------------------------------------------------------


def test_portal_requires_billing_enabled(db_session: Session) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not configured"):
        BillingService(db_session).create_portal_session(user.id)


def test_portal_requires_customer(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="No billing account"):
        BillingService(db_session).create_portal_session(user.id)
