"""Billing request/response schemas."""

from typing import Literal

from pydantic import BaseModel, Field

from app.core.plans import PlanId


class CheckoutRequest(BaseModel):
    plan: Literal["starter", "plus", "pro"] = "pro"
    billing_period: Literal["monthly", "annual"] = "monthly"
    promo_code: str | None = None


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


class BillingStatusRead(BaseModel):
    configured: bool
    plan: PlanId
    subscription_status: str | None = None
    has_stripe_subscription: bool
    can_checkout: bool
    can_manage: bool
    trial_days: int = Field(default=14, ge=0)
