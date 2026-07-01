"""PromoCode: discount/trial offers redeemable at checkout."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.promo_redemption import PromoRedemption


class PromoCode(Base, TimestampMixin):
    __tablename__ = "promo_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    promo_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # percent (1-100), cents, trial days, or unused for plan_upgrade
    value_int: Mapped[int] = mapped_column(Integer, nullable=False)
    # Target plan when promo_type is plan_upgrade (pro / team).
    plan_target: Mapped[str | None] = mapped_column(String(20), nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redemption_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    one_per_user: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # When set, only users on these plans may redeem (e.g. ["free"]).
    eligible_plans: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    stripe_coupon_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_promotion_code_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    redemptions: Mapped[list["PromoRedemption"]] = relationship(
        back_populates="promo_code", cascade="all, delete-orphan"
    )
