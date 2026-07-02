"""Promo code service and API tests."""

from __future__ import annotations

import contextlib
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.main import app
from app.models.promo_code import PromoCode
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from app.services.promo_codes import PromoCodeService
from tests.conftest import register_and_login


@pytest.fixture
def billing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_promo")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_promo")
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_annual", "price_starter_annual")
    monkeypatch.setattr(settings, "stripe_price_plus_monthly", "price_plus_monthly")
    monkeypatch.setattr(settings, "stripe_price_plus_annual", "price_plus_annual")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_annual", "price_pro_annual")


@contextmanager
def _with_client_db():
    """Yield the TestClient's shared DB session."""
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    try:
        yield db
        db.commit()
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


def _add_promo(
    db_session: Session,
    *,
    code: str = "SAVE20",
    promo_type: str = "percent_off",
    value_int: int = 20,
    active: bool = True,
    max_redemptions: int | None = None,
    expires_at: datetime | None = None,
    one_per_user: bool = True,
    eligible_plans: list[str] | None = None,
    stripe_promotion_code_id: str | None = "promo_stripe_1",
) -> PromoCode:
    promo = PromoCode(
        code=code,
        promo_type=promo_type,
        value_int=value_int,
        active=active,
        max_redemptions=max_redemptions,
        expires_at=expires_at,
        one_per_user=one_per_user,
        eligible_plans=eligible_plans,
        stripe_promotion_code_id=stripe_promotion_code_id,
        stripe_coupon_id="coupon_stripe_1",
    )
    added = PromoCodeRepository(db_session).add(promo)
    db_session.commit()
    return added


def test_validate_valid_promo(db_session: Session) -> None:
    user = User(email="promo@example.com", password_hash="hash", plan="free")
    UserRepository(db_session).add(user)
    _add_promo(db_session)

    result = PromoCodeService(db_session).validate_for_user(user.id, "save20")
    assert result.code == "SAVE20"
    assert result.percent_off == 20
    assert result.description == "20% off"


def test_validate_expired_promo(db_session: Session) -> None:
    user = User(email="expired@example.com", password_hash="hash", plan="free")
    UserRepository(db_session).add(user)
    _add_promo(
        db_session,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    with pytest.raises(ValidationError, match="expired"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_validate_ineligible_plan(db_session: Session) -> None:
    user = User(email="pro@example.com", password_hash="hash", plan="pro")
    UserRepository(db_session).add(user)
    _add_promo(db_session, eligible_plans=["free"])

    with pytest.raises(ValidationError, match="not eligible"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_validate_already_redeemed(db_session: Session) -> None:
    user = User(email="redeemed@example.com", password_hash="hash", plan="free")
    UserRepository(db_session).add(user)
    promo = _add_promo(db_session)
    PromoCodeService(db_session).record_redemption(promo, user.id)

    with pytest.raises(ValidationError, match="already redeemed"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


@patch("app.services.promo_codes.stripe.PromotionCode.create")
@patch("app.services.promo_codes.stripe.Coupon.create")
def test_admin_create_promo_with_stripe(
    mock_coupon: MagicMock,
    mock_promotion: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="admin@example.com", password="password123")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    client.patch(
        f"/api/v1/admin/users/{me['id']}",
        headers=headers,
        json={"is_admin": True},
    )

    mock_coupon.return_value = MagicMock(id="coupon_new")
    mock_promotion.return_value = MagicMock(id="promo_new")

    resp = client.post(
        "/api/v1/admin/promo-codes",
        headers=headers,
        json={
            "code": "launch-30",
            "promo_type": "percent_off",
            "value_int": 30,
            "max_redemptions": 100,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "LAUNCH-30"
    assert body["stripe_coupon_id"] == "coupon_new"
    assert body["stripe_promotion_code_id"] == "promo_new"


def test_validate_promo_api(client: TestClient) -> None:
    headers = register_and_login(client, email="validate@example.com", password="password123")
    with _with_client_db() as db:
        _add_promo(db, code="TRIAL60", promo_type="free_trial_days", value_int=60)

    resp = client.post(
        "/api/v1/billing/promo/validate",
        headers=headers,
        json={"code": "trial60"},
    )
    assert resp.status_code == 200
    assert resp.json()["trial_days"] == 60


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_checkout_applies_promo_discount(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="checkout@example.com", password="password123")
    with _with_client_db() as db:
        _add_promo(db)
    mock_customer_create.return_value = MagicMock(id="cus_promo")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.test/session")

    resp = client.post(
        "/api/v1/billing/checkout",
        headers=headers,
        json={"plan": "pro", "billing_period": "monthly", "promo_code": "SAVE20"},
    )
    assert resp.status_code == 200
    call_kwargs = mock_session_create.call_args.kwargs
    assert call_kwargs["discounts"] == [{"promotion_code": "promo_stripe_1"}]
    assert call_kwargs["metadata"]["promo_code_id"]


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_checkout_applies_trial_promo(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="trial@example.com", password="password123")
    with _with_client_db() as db:
        _add_promo(
            db,
            code="TRIAL90",
            promo_type="free_trial_days",
            value_int=90,
            stripe_promotion_code_id=None,
        )
    mock_customer_create.return_value = MagicMock(id="cus_trial")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.test/session")

    resp = client.post(
        "/api/v1/billing/checkout",
        headers=headers,
        json={"plan": "pro", "billing_period": "monthly", "promo_code": "TRIAL90"},
    )
    assert resp.status_code == 200
    call_kwargs = mock_session_create.call_args.kwargs
    assert call_kwargs["subscription_data"]["trial_period_days"] == 90
    assert "discounts" not in call_kwargs


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_checkout_applies_trial_promo_on_starter(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="trial-starter@example.com", password="password123")
    with _with_client_db() as db:
        _add_promo(
            db,
            code="STARTER30",
            promo_type="free_trial_days",
            value_int=30,
            stripe_promotion_code_id=None,
        )
    mock_customer_create.return_value = MagicMock(id="cus_trial_starter")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.test/starter")

    resp = client.post(
        "/api/v1/billing/checkout",
        headers=headers,
        json={"plan": "starter", "billing_period": "monthly", "promo_code": "STARTER30"},
    )
    assert resp.status_code == 200
    call_kwargs = mock_session_create.call_args.kwargs
    assert call_kwargs["subscription_data"]["trial_period_days"] == 30
