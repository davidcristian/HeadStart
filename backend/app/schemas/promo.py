"""Promo code request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.plans import PlanId

PromoType = Literal["percent_off", "fixed_amount", "free_trial_days", "plan_upgrade"]


class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    promo_type: PromoType
    value_int: int = Field(ge=1)
    plan_target: PlanId | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None
    one_per_user: bool = True
    eligible_plans: list[PlanId] | None = None


class PromoCodeUpdate(BaseModel):
    active: bool | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class PromoCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    promo_type: PromoType
    value_int: int
    plan_target: PlanId | None = None
    max_redemptions: int | None
    redemption_count: int
    expires_at: datetime | None
    active: bool
    one_per_user: bool
    eligible_plans: list[PlanId] | None
    stripe_coupon_id: str | None
    stripe_promotion_code_id: str | None
    created_at: datetime


class PromoRedemptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    promo_code_id: int
    user_id: int
    stripe_checkout_session_id: str | None
    created_at: datetime


class PromoValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class PromoValidateResponse(BaseModel):
    code: str
    promo_type: PromoType
    description: str
    trial_days: int | None = None
    percent_off: int | None = None
    amount_off_cents: int | None = None
    plan_target: PlanId | None = None
