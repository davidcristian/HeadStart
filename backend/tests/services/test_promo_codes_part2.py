"""Promo validate/resolve/describe/Stripe-param tests (service + repo)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.promo_code import PromoCode
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from app.schemas.promo import PromoCodeCreate
from app.services.promo_codes import PromoCodeService


@pytest.fixture
def billing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_promo_svc")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_promo_svc")
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_annual", "price_starter_annual")
    monkeypatch.setattr(settings, "stripe_price_plus_monthly", "price_plus_monthly")
    monkeypatch.setattr(settings, "stripe_price_plus_annual", "price_plus_annual")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_annual", "price_pro_annual")


def _user(db_session: Session, *, email: str = "promo-svc@example.com", plan: str = "free") -> User:
    return UserRepository(db_session).add(User(email=email, password_hash="hash", plan=plan))


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
    return PromoCodeRepository(db_session).add(
        PromoCode(
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
    )


# --- validate / resolve ---------------------------------------------------


def test_validate_unknown_code_raises(db_session: Session) -> None:
    user = _user(db_session)
    with pytest.raises(ValidationError, match="Invalid promo code"):
        PromoCodeService(db_session).validate_for_user(user.id, "NOPE")


def test_validate_missing_user_raises(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        PromoCodeService(db_session).validate_for_user(999999, "SAVE20")


def test_validate_rate_limited(db_session: Session) -> None:
    user = _user(db_session)
    _add_promo(db_session)
    repo = PromoCodeRepository(db_session)
    for _ in range(10):
        repo.record_validation_attempt(user.id, "SAVE20")
    db_session.flush()
    with pytest.raises(ValidationError, match="Too many promo code attempts"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_validate_inactive_promo_rejected(db_session: Session) -> None:
    user = _user(db_session)
    _add_promo(db_session, active=False)
    with pytest.raises(ValidationError, match="no longer active"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_validate_expired_naive_datetime_rejected(db_session: Session) -> None:
    user = _user(db_session)
    # Naive (tz-less) expiry in the past exercises the tz-normalization branch.
    _add_promo(db_session, expires_at=datetime.utcnow() - timedelta(days=1))
    with pytest.raises(ValidationError, match="expired"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_validate_fully_redeemed_cap_rejected(db_session: Session) -> None:
    user = _user(db_session)
    promo = _add_promo(db_session, max_redemptions=1)
    promo.redemption_count = 1
    db_session.flush()
    with pytest.raises(ValidationError, match="fully redeemed"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_validate_rejected_for_active_subscriber(db_session: Session) -> None:
    user = _user(db_session)
    user.subscription_status = "active"
    db_session.flush()
    _add_promo(db_session, one_per_user=False)
    with pytest.raises(ValidationError, match="already have an active subscription"):
        PromoCodeService(db_session).validate_for_user(user.id, "SAVE20")


def test_resolve_for_checkout_unknown_code_raises(db_session: Session) -> None:
    user = _user(db_session)
    with pytest.raises(ValidationError, match="Invalid promo code"):
        PromoCodeService(db_session).resolve_for_checkout(user.id, "NOPE")


def test_reserve_uncapped_promo_second_reservation_releases_slot(db_session: Session) -> None:
    # A user who already holds a reservation must not consume a second slot.
    promo = _add_promo(
        db_session,
        code="TRIALREL",
        promo_type="free_trial_days",
        value_int=7,
        max_redemptions=5,
        one_per_user=False,
        stripe_promotion_code_id=None,
    )
    user = _user(db_session)
    service = PromoCodeService(db_session)

    service.resolve_for_checkout(user.id, "TRIALREL")
    db_session.flush()
    db_session.refresh(promo)
    assert promo.redemption_count == 1

    # Second resolve for the same user reserves a global slot then releases it
    # because the per-user row already exists.
    service.resolve_for_checkout(user.id, "TRIALREL")
    db_session.flush()
    db_session.refresh(promo)
    assert promo.redemption_count == 1


# --- describe -------------------------------------------------------------


def test_describe_variants(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    assert (
        service.describe(PromoCode(code="A", promo_type="percent_off", value_int=25)) == "25% off"
    )
    assert (
        service.describe(PromoCode(code="B", promo_type="fixed_amount", value_int=1000))
        == "$10 off"
    )
    assert (
        service.describe(PromoCode(code="C", promo_type="fixed_amount", value_int=1550))
        == "$15.50 off"
    )
    assert (
        service.describe(PromoCode(code="D", promo_type="free_trial_days", value_int=14))
        == "14-day free trial"
    )
    assert (
        service.describe(
            PromoCode(code="E", promo_type="plan_upgrade", value_int=1, plan_target="pro")
        )
        == "Upgrade to Pro"
    )
    # Fallback for an unrecognized/unset shape.
    assert (
        service.describe(PromoCode(code="F", promo_type="plan_upgrade", value_int=1))
        == "Promotional offer"
    )


# --- Stripe coupon params -------------------------------------------------


@patch("app.services.promo_codes.stripe.PromotionCode.create")
@patch("app.services.promo_codes.stripe.Coupon.create")
def test_create_fixed_amount_stripe_coupon_params(
    mock_coupon: MagicMock,
    mock_promotion: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    mock_coupon.return_value = MagicMock(id="coupon_fa")
    mock_promotion.return_value = MagicMock(id="promo_fa")
    PromoCodeService(db_session).create_code(
        PromoCodeCreate(code="TENOFF", promo_type="fixed_amount", value_int=1000)
    )
    params = mock_coupon.call_args.kwargs
    assert params["amount_off"] == 1000
    assert params["currency"] == "usd"


@patch("app.services.promo_codes.stripe.PromotionCode.create")
@patch("app.services.promo_codes.stripe.Coupon.create")
def test_create_plan_upgrade_stripe_coupon_params(
    mock_coupon: MagicMock,
    mock_promotion: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    mock_coupon.return_value = MagicMock(id="coupon_pu")
    mock_promotion.return_value = MagicMock(id="promo_pu")
    PromoCodeService(db_session).create_code(
        PromoCodeCreate(
            code="UPGRADEPRO", promo_type="plan_upgrade", value_int=1, plan_target="pro"
        )
    )
    params = mock_coupon.call_args.kwargs
    assert params["percent_off"] == 100


def test_stripe_coupon_params_unsupported_type_raises(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    with pytest.raises(ValidationError, match="Unsupported promo type"):
        service._stripe_coupon_params(
            PromoCode(code="FT", promo_type="free_trial_days", value_int=7)
        )


def test_reserve_uncapped_promo_raises_when_slot_unavailable(db_session: Session) -> None:
    _add_promo(
        db_session,
        code="TRIALFULL",
        promo_type="free_trial_days",
        value_int=7,
        max_redemptions=1,
        stripe_promotion_code_id=None,
    )
    user = _user(db_session)
    service = PromoCodeService(db_session)
    # _assert_redeemable passes (count < max) but the atomic global reservation
    # loses the race and returns False.
    with (
        patch.object(PromoCodeRepository, "reserve_global_slot", return_value=False),
        pytest.raises(ValidationError, match="fully redeemed"),
    ):
        service.resolve_for_checkout(user.id, "TRIALFULL")


def test_assert_redeemable_accepts_future_aware_expiry(db_session: Session) -> None:
    # SQLite drops tzinfo on round-trip, so build an in-memory promo carrying an
    # aware expiry to exercise the "already tz-aware" branch directly.
    user = _user(db_session)
    promo = PromoCode(
        code="AWARE",
        promo_type="percent_off",
        value_int=10,
        active=True,
        one_per_user=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    # No exception -> future aware expiry is accepted.
    PromoCodeService(db_session)._assert_redeemable(promo, user)


def test_create_code_accepts_valid_eligible_plans(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    read = service.create_code(
        PromoCodeCreate(
            code="PLUSONLY",
            promo_type="percent_off",
            value_int=10,
            eligible_plans=["free", "starter"],
        )
    )
    assert read.eligible_plans == ["free", "starter"]


def test_require_user_missing_raises(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        PromoCodeService(db_session)._require_user(999999)
