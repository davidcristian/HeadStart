"""Billing service unit tests."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.repositories.users import UserRepository
from app.services.billing import BillingService


@pytest.fixture
def billing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_unit")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_unit")
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
    plan = service._plan_from_subscription(
        {
            "status": "active",
            "metadata": {},
            "items": {"data": [{"price": {"id": "price_pro_annual"}}]},
        },
        "active",
    )
    assert plan == "pro"
