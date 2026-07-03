"""Direct unit tests for PromoCodeRepository accessors."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository


def _promo(session: Session, code: str = "SAVE20") -> PromoCode:
    return PromoCodeRepository(session).add(
        PromoCode(code=code, promo_type="percent_off", value_int=20)
    )


def test_get_and_list_all(db_session: Session) -> None:
    repo = PromoCodeRepository(db_session)
    a = _promo(db_session, "A")
    b = _promo(db_session, "B")

    assert repo.get(a.id).id == a.id
    ids = {p.id for p in repo.list_all()}
    assert ids == {a.id, b.id}


def test_update_fields(db_session: Session) -> None:
    repo = PromoCodeRepository(db_session)
    promo = _promo(db_session)

    updated = repo.update(promo, value_int=50, active=False)
    db_session.refresh(promo)
    assert updated.value_int == 50
    assert promo.active is False


def test_list_redemptions(db_session: Session) -> None:
    repo = PromoCodeRepository(db_session)
    promo = _promo(db_session)
    user = UserRepository(db_session).add(User(email="r@example.test", password_hash="x"))
    repo.add_redemption(PromoRedemption(promo_code_id=promo.id, user_id=user.id))

    rows = repo.list_redemptions(promo.id)
    assert len(rows) == 1
    assert rows[0].user_id == user.id


def test_release_global_slot(db_session: Session) -> None:
    repo = PromoCodeRepository(db_session)
    promo = _promo(db_session)
    repo.increment_redemption_count(promo.id)
    db_session.flush()
    db_session.refresh(promo)
    assert promo.redemption_count == 1

    repo.release_global_slot(promo.id)
    db_session.flush()
    db_session.refresh(promo)
    assert promo.redemption_count == 0
