"""Data access for promo codes and redemptions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.promo_validation_attempt import PromoValidationAttempt


def normalize_promo_code(code: str) -> str:
    """Normalize user-entered codes to a canonical uppercase form."""
    return code.strip().upper()


class PromoCodeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, promo_id: int) -> PromoCode | None:
        return self.session.get(PromoCode, promo_id)

    def get_by_code(self, code: str) -> PromoCode | None:
        normalized = normalize_promo_code(code)
        return self.session.scalar(select(PromoCode).where(PromoCode.code == normalized))

    def list_all(self) -> list[PromoCode]:
        return list(self.session.scalars(select(PromoCode).order_by(PromoCode.created_at.desc())))

    def add(self, promo: PromoCode) -> PromoCode:
        self.session.add(promo)
        self.session.flush()
        return promo

    def update(self, promo: PromoCode, **fields: object) -> PromoCode:
        for key, value in fields.items():
            setattr(promo, key, value)
        self.session.flush()
        return promo

    def increment_redemption_count(self, promo_id: int) -> None:
        self.session.execute(
            update(PromoCode)
            .where(PromoCode.id == promo_id)
            .values(redemption_count=PromoCode.redemption_count + 1)
        )

    def count_user_redemptions(self, promo_id: int, user_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(PromoRedemption)
                .where(PromoRedemption.promo_code_id == promo_id)
                .where(PromoRedemption.user_id == user_id)
            )
            or 0
        )

    def list_redemptions(self, promo_id: int) -> list[PromoRedemption]:
        return list(
            self.session.scalars(
                select(PromoRedemption)
                .where(PromoRedemption.promo_code_id == promo_id)
                .order_by(PromoRedemption.created_at.desc())
            )
        )

    def add_redemption(self, redemption: PromoRedemption) -> PromoRedemption:
        self.session.add(redemption)
        self.session.flush()
        return redemption

    def record_validation_attempt(self, user_id: int, code: str) -> None:
        attempt = PromoValidationAttempt(
            user_id=user_id,
            code_entered=normalize_promo_code(code),
        )
        self.session.add(attempt)
        self.session.flush()

    def count_recent_validation_attempts(self, user_id: int, *, window_minutes: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(PromoValidationAttempt)
                .where(PromoValidationAttempt.user_id == user_id)
                .where(PromoValidationAttempt.created_at >= cutoff)
            )
            or 0
        )
