"""Promo code business logic: validation, admin CRUD, and Stripe sync."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.plans import VALID_PLANS
from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository, normalize_promo_code
from app.repositories.users import UserRepository
from app.schemas.promo import (
    PromoCodeCreate,
    PromoCodeRead,
    PromoCodeUpdate,
    PromoRedemptionRead,
    PromoValidateResponse,
)

logger = logging.getLogger(__name__)

_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]*[A-Z0-9]$|^[A-Z0-9]$")
_VALIDATION_WINDOW_MINUTES = 15
_MAX_VALIDATION_ATTEMPTS = 10


class PromoCodeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.promos = PromoCodeRepository(session)
        self.users = UserRepository(session)
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key

    def list_codes(self) -> list[PromoCodeRead]:
        """Return every promo code for the admin panel."""
        return [PromoCodeRead.model_validate(p) for p in self.promos.list_all()]

    def list_redemptions(self, promo_id: int) -> list[PromoRedemptionRead]:
        """Return redemption audit rows for a promo code."""
        promo = self.promos.get(promo_id)
        if promo is None:
            raise NotFoundError("Promo code not found.")
        redemptions = self.promos.list_redemptions(promo_id)
        return [PromoRedemptionRead.model_validate(r) for r in redemptions]

    def create_code(self, data: PromoCodeCreate) -> PromoCodeRead:
        """Create a promo code and optionally sync it to Stripe."""
        code = self._validate_code_format(data.code)
        self._validate_create_payload(data)
        if self.promos.get_by_code(code):
            raise ConflictError(f"Promo code '{code}' already exists.")

        promo = PromoCode(
            code=code,
            promo_type=data.promo_type,
            value_int=data.value_int,
            plan_target=data.plan_target,
            max_redemptions=data.max_redemptions,
            expires_at=data.expires_at,
            one_per_user=data.one_per_user,
            eligible_plans=data.eligible_plans,
        )
        if settings.billing_enabled and data.promo_type in {
            "percent_off",
            "fixed_amount",
            "plan_upgrade",
        }:
            coupon_id, promotion_id = self._create_stripe_objects(promo)
            promo.stripe_coupon_id = coupon_id
            promo.stripe_promotion_code_id = promotion_id

        self.promos.add(promo)
        return PromoCodeRead.model_validate(promo)

    def update_code(self, promo_id: int, data: PromoCodeUpdate) -> PromoCodeRead:
        """Update mutable promo code fields (retire, extend expiry, etc.)."""
        promo = self.promos.get(promo_id)
        if promo is None:
            raise NotFoundError("Promo code not found.")
        updates = data.model_dump(exclude_unset=True)
        if updates:
            self.promos.update(promo, **updates)
        return PromoCodeRead.model_validate(promo)

    def validate_for_user(self, user_id: int, code: str) -> PromoValidateResponse:
        """Check whether a promo code can be redeemed by the user."""
        user = self._require_user(user_id)
        self._enforce_validation_rate_limit(user_id)
        normalized = normalize_promo_code(code)
        self.promos.record_validation_attempt(user_id, normalized)

        promo = self.promos.get_by_code(normalized)
        if promo is None:
            raise ValidationError("Invalid promo code.")
        self._assert_redeemable(promo, user)
        return self._to_validate_response(promo)

    def resolve_for_checkout(self, user_id: int, code: str) -> PromoCode:
        """Validate and return a promo for checkout (does not record redemption yet)."""
        user = self._require_user(user_id)
        promo = self.promos.get_by_code(code)
        if promo is None:
            raise ValidationError("Invalid promo code.")
        self._assert_redeemable(promo, user)
        return promo

    def record_redemption(
        self,
        promo: PromoCode,
        user_id: int,
        *,
        checkout_session_id: str | None = None,
    ) -> None:
        """Persist a redemption and bump the global counter."""
        if self.promos.count_user_redemptions(promo.id, user_id) > 0:
            return
        self.promos.add_redemption(
            PromoRedemption(
                promo_code_id=promo.id,
                user_id=user_id,
                stripe_checkout_session_id=checkout_session_id,
            )
        )
        self.promos.increment_redemption_count(promo.id)

    def describe(self, promo: PromoCode) -> str:
        """Human-readable summary for UI and notifications."""
        if promo.promo_type == "percent_off":
            return f"{promo.value_int}% off"
        if promo.promo_type == "fixed_amount":
            dollars = promo.value_int / 100
            if dollars == int(dollars):
                return f"${int(dollars)} off"
            return f"${dollars:.2f} off"
        if promo.promo_type == "free_trial_days":
            return f"{promo.value_int}-day free trial"
        if promo.promo_type == "plan_upgrade" and promo.plan_target:
            return f"Upgrade to {promo.plan_target.title()}"
        return "Promotional offer"

    def _to_validate_response(self, promo: PromoCode) -> PromoValidateResponse:
        return PromoValidateResponse(
            code=promo.code,
            promo_type=promo.promo_type,
            description=self.describe(promo),
            trial_days=promo.value_int if promo.promo_type == "free_trial_days" else None,
            percent_off=promo.value_int if promo.promo_type == "percent_off" else None,
            amount_off_cents=promo.value_int if promo.promo_type == "fixed_amount" else None,
            plan_target=promo.plan_target if promo.promo_type == "plan_upgrade" else None,
        )

    def _assert_redeemable(self, promo: PromoCode, user: User) -> None:
        if not promo.active:
            raise ValidationError("This promo code is no longer active.")
        if promo.expires_at is not None:
            expires_at = promo.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                raise ValidationError("This promo code has expired.")
        if promo.max_redemptions is not None and promo.redemption_count >= promo.max_redemptions:
            raise ValidationError("This promo code has been fully redeemed.")
        if promo.eligible_plans and user.plan not in promo.eligible_plans:
            raise ValidationError("You are not eligible for this promo code.")
        if promo.one_per_user and self.promos.count_user_redemptions(promo.id, user.id) > 0:
            raise ValidationError("You have already redeemed this promo code.")
        if user.subscription_status and user.subscription_status in {"active", "trialing"}:
            raise ValidationError(
                "You already have an active subscription. Manage billing from Settings."
            )

    def _enforce_validation_rate_limit(self, user_id: int) -> None:
        attempts = self.promos.count_recent_validation_attempts(
            user_id, window_minutes=_VALIDATION_WINDOW_MINUTES
        )
        if attempts >= _MAX_VALIDATION_ATTEMPTS:
            raise ValidationError("Too many promo code attempts. Try again later.")

    def _validate_code_format(self, code: str) -> str:
        normalized = normalize_promo_code(code)
        if not _CODE_PATTERN.match(normalized):
            raise ValidationError(
                "Promo codes must be 1–64 characters: letters, numbers, and hyphens only."
            )
        return normalized

    def _validate_create_payload(self, data: PromoCodeCreate) -> None:
        if data.promo_type == "percent_off" and not 1 <= data.value_int <= 100:
            raise ValidationError("Percent off must be between 1 and 100.")
        if data.promo_type == "plan_upgrade":
            if not data.plan_target or data.plan_target not in VALID_PLANS:
                raise ValidationError("Plan upgrade promos require a valid plan_target.")
            if data.plan_target == "free":
                raise ValidationError("Plan upgrade cannot target the free plan.")
        if data.promo_type != "plan_upgrade" and data.plan_target is not None:
            raise ValidationError("plan_target is only valid for plan_upgrade promos.")
        if data.eligible_plans:
            for plan in data.eligible_plans:
                if plan not in VALID_PLANS:
                    raise ValidationError(f"Unknown eligible plan '{plan}'.")

    def _create_stripe_objects(self, promo: PromoCode) -> tuple[str, str]:
        coupon_params = self._stripe_coupon_params(promo)
        coupon = stripe.Coupon.create(**coupon_params)
        promotion_kwargs: dict[str, Any] = {
            "promotion": {"type": "coupon", "coupon": coupon.id},
            "code": promo.code,
            "metadata": {"promo_code_id": str(promo.id or "")},
        }
        if promo.max_redemptions is not None:
            promotion_kwargs["max_redemptions"] = promo.max_redemptions
        promotion = stripe.PromotionCode.create(**promotion_kwargs)
        return coupon.id, promotion.id

    def _stripe_coupon_params(self, promo: PromoCode) -> dict[str, Any]:
        if promo.promo_type == "percent_off":
            return {
                "percent_off": promo.value_int,
                "duration": "forever",
                "name": f"HeadStart {promo.code}",
            }
        if promo.promo_type == "fixed_amount":
            return {
                "amount_off": promo.value_int,
                "currency": "usd",
                "duration": "forever",
                "name": f"HeadStart {promo.code}",
            }
        if promo.promo_type == "plan_upgrade":
            return {
                "percent_off": 100,
                "duration": "forever",
                "name": f"HeadStart {promo.code} ({promo.plan_target})",
            }
        raise ValidationError("Unsupported promo type for Stripe coupon sync.")

    def _require_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user
