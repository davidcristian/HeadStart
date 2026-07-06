"""PromoRedemption: audit trail when a user redeems a promo code."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.promo_code import PromoCode
    from app.models.user import User


class PromoRedemption(Base):
    __tablename__ = "promo_redemption"
    # One redemption per user per promo: makes webhook retries / concurrent
    # deliveries a no-op instead of double-counting (see PromoCodeService).
    __table_args__ = (
        UniqueConstraint("promo_code_id", "user_id", name="uq_promo_redemption_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    promo_code_id: Mapped[int] = mapped_column(
        ForeignKey("promo_code.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    promo_code: Mapped["PromoCode"] = relationship(back_populates="redemptions")
    user: Mapped["User"] = relationship(back_populates="promo_redemptions")
