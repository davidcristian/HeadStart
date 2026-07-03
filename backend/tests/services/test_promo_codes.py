"""Promo redemption idempotency and cap-reservation tests (service + repo)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from app.schemas.promo import PromoCodeCreate, PromoCodeUpdate
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


def test_record_redemption_is_idempotent(db_session: Session) -> None:
    """A webhook retry must not create a second row or double the counter."""
    user = UserRepository(db_session).add(
        User(email="idem@example.com", password_hash="hash", plan="free")
    )
    promo = _add_promo(db_session)
    service = PromoCodeService(db_session)

    service.record_redemption(promo, user.id)
    service.record_redemption(promo, user.id)
    db_session.flush()

    repo = PromoCodeRepository(db_session)
    assert repo.count_user_redemptions(promo.id, user.id) == 1
    db_session.refresh(promo)
    assert promo.redemption_count == 1


def test_record_redemption_swallows_concurrent_duplicate(db_session: Session) -> None:
    """The unique constraint makes a raced duplicate a no-op, not a crash/double-count."""
    user = UserRepository(db_session).add(
        User(email="race@example.com", password_hash="hash", plan="free")
    )
    promo = _add_promo(db_session)
    repo = PromoCodeRepository(db_session)

    # The winning delivery already recorded the redemption + bumped the counter.
    repo.add_redemption(PromoRedemption(promo_code_id=promo.id, user_id=user.id))
    repo.increment_redemption_count(promo.id)
    db_session.flush()

    # A racing delivery whose read-guard saw no row must still not double-count.
    with patch.object(PromoCodeRepository, "count_user_redemptions", return_value=0):
        PromoCodeService(db_session).record_redemption(promo, user.id)
    db_session.flush()

    assert repo.count_user_redemptions(promo.id, user.id) == 1
    db_session.refresh(promo)
    assert promo.redemption_count == 1


def test_reserve_global_slot_enforces_cap(db_session: Session) -> None:
    """The atomic conditional bump refuses to overrun max_redemptions."""
    promo = _add_promo(
        db_session,
        code="TRIALCAP2",
        promo_type="free_trial_days",
        value_int=7,
        max_redemptions=2,
        stripe_promotion_code_id=None,
    )
    repo = PromoCodeRepository(db_session)
    assert repo.reserve_global_slot(promo.id, 2) is True
    assert repo.reserve_global_slot(promo.id, 2) is True
    assert repo.reserve_global_slot(promo.id, 2) is False
    db_session.refresh(promo)
    assert promo.redemption_count == 2


def test_free_trial_cap_reserved_at_checkout(db_session: Session) -> None:
    """A capped free_trial_days promo (no Stripe cap) enforces the cap at checkout."""
    promo = _add_promo(
        db_session,
        code="TRIALCAP",
        promo_type="free_trial_days",
        value_int=30,
        max_redemptions=1,
        stripe_promotion_code_id=None,
    )
    users = UserRepository(db_session)
    u1 = users.add(User(email="cap1@example.com", password_hash="hash", plan="free"))
    u2 = users.add(User(email="cap2@example.com", password_hash="hash", plan="free"))
    service = PromoCodeService(db_session)

    service.resolve_for_checkout(u1.id, "TRIALCAP")  # reserves the only slot now
    db_session.flush()
    db_session.refresh(promo)
    assert promo.redemption_count == 1
    assert PromoCodeRepository(db_session).count_user_redemptions(promo.id, u1.id) == 1

    with pytest.raises(ValidationError, match="fully redeemed"):
        service.resolve_for_checkout(u2.id, "TRIALCAP")


# --- listing / redemptions ------------------------------------------------


def test_list_codes(db_session: Session) -> None:
    _add_promo(db_session)
    codes = PromoCodeService(db_session).list_codes()
    assert [c.code for c in codes] == ["SAVE20"]


def test_list_redemptions(db_session: Session) -> None:
    user = _user(db_session)
    promo = _add_promo(db_session)
    service = PromoCodeService(db_session)
    service.record_redemption(promo, user.id)
    db_session.flush()

    rows = service.list_redemptions(promo.id)
    assert len(rows) == 1
    assert rows[0].user_id == user.id


def test_list_redemptions_missing_promo_raises(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        PromoCodeService(db_session).list_redemptions(999999)


# --- create / update ------------------------------------------------------


def test_create_code_without_stripe_sync(db_session: Session) -> None:
    # billing disabled -> no Stripe objects created.
    service = PromoCodeService(db_session)
    read = service.create_code(
        PromoCodeCreate(code="plain-10", promo_type="percent_off", value_int=10)
    )
    assert read.code == "PLAIN-10"
    assert read.stripe_coupon_id is None


@patch("app.services.promo_codes.stripe.PromotionCode.create")
@patch("app.services.promo_codes.stripe.Coupon.create")
def test_create_code_with_stripe_sync_and_cap(
    mock_coupon: MagicMock,
    mock_promotion: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    mock_coupon.return_value = MagicMock(id="coupon_x")
    mock_promotion.return_value = MagicMock(id="promo_x")
    service = PromoCodeService(db_session)

    read = service.create_code(
        PromoCodeCreate(
            code="LAUNCH50",
            promo_type="percent_off",
            value_int=50,
            max_redemptions=25,
        )
    )
    assert read.stripe_coupon_id == "coupon_x"
    assert read.stripe_promotion_code_id == "promo_x"
    # The cap is forwarded to the Stripe promotion code.
    assert mock_promotion.call_args.kwargs["max_redemptions"] == 25


def test_create_code_conflict_raises(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    service.create_code(PromoCodeCreate(code="DUPE", promo_type="percent_off", value_int=10))
    with pytest.raises(ConflictError, match="already exists"):
        service.create_code(PromoCodeCreate(code="dupe", promo_type="percent_off", value_int=10))


def test_create_code_rejects_bad_format(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    with pytest.raises(ValidationError, match="Promo codes must be"):
        service.create_code(PromoCodeCreate(code="-bad-", promo_type="percent_off", value_int=10))


def test_create_code_rejects_percent_out_of_range(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    with pytest.raises(ValidationError, match="between 1 and 100"):
        service.create_code(PromoCodeCreate(code="TOOBIG", promo_type="percent_off", value_int=150))


def test_create_code_plan_upgrade_requires_valid_target(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    data = PromoCodeCreate.model_construct(
        code="UPG", promo_type="plan_upgrade", value_int=1, plan_target=None
    )
    with pytest.raises(ValidationError, match="valid plan_target"):
        service.create_code(data)


def test_create_code_plan_upgrade_cannot_target_free(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    data = PromoCodeCreate.model_construct(
        code="UPGF", promo_type="plan_upgrade", value_int=1, plan_target="free"
    )
    with pytest.raises(ValidationError, match="cannot target the free plan"):
        service.create_code(data)


def test_create_code_plan_target_only_for_upgrade(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    data = PromoCodeCreate.model_construct(
        code="PT", promo_type="percent_off", value_int=10, plan_target="pro"
    )
    with pytest.raises(ValidationError, match="only valid for plan_upgrade"):
        service.create_code(data)


def test_create_code_rejects_unknown_eligible_plan(db_session: Session) -> None:
    service = PromoCodeService(db_session)
    data = PromoCodeCreate.model_construct(
        code="ELIG", promo_type="percent_off", value_int=10, eligible_plans=["gold"]
    )
    with pytest.raises(ValidationError, match="Unknown eligible plan"):
        service.create_code(data)


def test_update_code_applies_fields(db_session: Session) -> None:
    promo = _add_promo(db_session)
    service = PromoCodeService(db_session)
    read = service.update_code(promo.id, PromoCodeUpdate(active=False, max_redemptions=5))
    assert read.active is False
    assert read.max_redemptions == 5


def test_update_code_no_fields_is_noop(db_session: Session) -> None:
    promo = _add_promo(db_session)
    service = PromoCodeService(db_session)
    read = service.update_code(promo.id, PromoCodeUpdate())
    assert read.code == promo.code


def test_update_code_missing_raises(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        PromoCodeService(db_session).update_code(999999, PromoCodeUpdate(active=False))
