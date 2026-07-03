"""Promo redemption idempotency and cap-reservation tests (service + repo)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from app.services.promo_codes import PromoCodeService


def _add_promo(
    db_session: Session,
    *,
    code: str = "SAVE20",
    promo_type: str = "percent_off",
    value_int: int = 20,
    max_redemptions: int | None = None,
    stripe_promotion_code_id: str | None = "promo_stripe_1",
) -> PromoCode:
    return PromoCodeRepository(db_session).add(
        PromoCode(
            code=code,
            promo_type=promo_type,
            value_int=value_int,
            max_redemptions=max_redemptions,
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
