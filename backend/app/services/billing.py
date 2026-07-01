"""Stripe billing: checkout, customer portal, and subscription webhooks."""

from __future__ import annotations

import logging
from typing import Any

import stripe
from sqlalchemy.orm import Session

from app.core.billing_prices import (
    BillingPeriod,
    plan_for_price_id,
    price_id_for,
    subscription_grants_plan,
)
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.plans import VALID_PLANS, PlanId
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.billing import BillingStatusRead

logger = logging.getLogger(__name__)

_CHECKOUT_PLANS: frozenset[str] = frozenset({"pro"})


class BillingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key

    def status(self, user_id: int) -> BillingStatusRead:
        """Return billing capabilities and subscription state for the signed-in user."""
        user = self._require_user(user_id)
        configured = settings.billing_enabled
        has_subscription = bool(user.stripe_subscription_id)
        active_subscription = bool(
            user.subscription_status and subscription_grants_plan(user.subscription_status)
        )
        return BillingStatusRead(
            configured=configured,
            plan=self._plan_id(user.plan),
            subscription_status=user.subscription_status,
            has_stripe_subscription=has_subscription,
            can_checkout=configured and not active_subscription and user.plan != "team",
            can_manage=configured and bool(user.stripe_customer_id),
            trial_days=settings.stripe_trial_days,
        )

    def create_checkout_session(
        self, user_id: int, *, plan: str, billing_period: BillingPeriod
    ) -> str:
        """Start a Stripe Checkout session and return its hosted URL."""
        self._require_billing_enabled()
        if plan not in _CHECKOUT_PLANS:
            raise ValidationError("Only the Pro plan is available for self-serve checkout.")
        user = self._require_user(user_id)
        if user.plan == "team":
            raise ValidationError(
                "Team plans are arranged manually. Contact support to change plans."
            )
        if user.subscription_status and subscription_grants_plan(user.subscription_status):
            raise ValidationError(
                "You already have an active subscription. Manage billing from Settings."
            )

        price_id = price_id_for("pro", billing_period)
        if not price_id:
            raise ValidationError("Billing is not fully configured for this plan.")

        customer_id = self._ensure_customer(user)
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.frontend_base_url}/app/settings?billing=success",
            cancel_url=f"{settings.frontend_base_url}/app/settings?billing=cancel",
            client_reference_id=str(user.id),
            metadata={"user_id": str(user.id), "plan": plan},
            subscription_data={
                "metadata": {"user_id": str(user.id), "plan": plan},
                **(
                    {"trial_period_days": settings.stripe_trial_days}
                    if settings.stripe_trial_days > 0
                    else {}
                ),
            },
        )
        if not session.url:
            raise ValidationError("Stripe did not return a checkout URL.")
        return session.url

    def create_portal_session(self, user_id: int) -> str:
        """Open the Stripe customer portal for subscription management."""
        self._require_billing_enabled()
        user = self._require_user(user_id)
        if not user.stripe_customer_id:
            raise ValidationError("No billing account found. Subscribe to a paid plan first.")
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{settings.frontend_base_url}/app/settings",
        )
        if not session.url:
            raise ValidationError("Stripe did not return a portal URL.")
        return session.url

    def handle_webhook(self, payload: bytes, signature: str | None) -> None:
        """Apply Stripe subscription lifecycle events to local user records."""
        self._require_billing_enabled()
        if not signature:
            raise ValidationError("Missing Stripe-Signature header.")
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )
        except ValueError as exc:
            raise ValidationError("Invalid webhook payload.") from exc
        except stripe.SignatureVerificationError as exc:
            raise ValidationError("Invalid webhook signature.") from exc

        event_type = event["type"]
        data_object = event["data"]["object"]

        if event_type == "checkout.session.completed":
            self._on_checkout_completed(data_object)
        elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            self._on_subscription_updated(data_object)
        elif event_type == "customer.subscription.deleted":
            self._on_subscription_deleted(data_object)

    def _on_checkout_completed(self, session: dict[str, Any]) -> None:
        user = self._user_from_reference(session)
        if user is None:
            logger.warning("checkout.session.completed without a matching user")
            return
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        updates: dict[str, str | None] = {}
        if isinstance(customer_id, str):
            updates["stripe_customer_id"] = customer_id
        if isinstance(subscription_id, str):
            updates["stripe_subscription_id"] = subscription_id
        if updates:
            self.users.update_billing(user, **updates)

    def _on_subscription_updated(self, subscription: dict[str, Any]) -> None:
        user = self._user_for_subscription(subscription)
        if user is None:
            logger.warning(
                "subscription update for unknown customer %s", subscription.get("customer")
            )
            return
        status = str(subscription.get("status") or "")
        plan = self._plan_from_subscription(subscription, status)
        self.users.update_billing(
            user,
            stripe_subscription_id=str(subscription.get("id") or user.stripe_subscription_id or ""),
            subscription_status=status or None,
            plan=plan,
        )

    def _on_subscription_deleted(self, subscription: dict[str, Any]) -> None:
        user = self._user_for_subscription(subscription)
        if user is None:
            return
        self.users.update_billing(
            user,
            stripe_subscription_id=None,
            subscription_status="canceled",
            plan="free",
        )

    def _plan_from_subscription(self, subscription: dict[str, Any], status: str) -> PlanId:
        if not subscription_grants_plan(status):
            return "free"
        items = subscription.get("items", {}).get("data", [])
        if not items:
            return "pro"
        price = items[0].get("price", {})
        price_id = price.get("id")
        if isinstance(price_id, str):
            resolved = plan_for_price_id(price_id)
            if resolved:
                return resolved
        metadata_plan = subscription.get("metadata", {}).get("plan")
        if isinstance(metadata_plan, str) and metadata_plan in VALID_PLANS:
            return metadata_plan  # type: ignore[return-value]
        return "pro"

    def _user_from_reference(self, session: dict[str, Any]) -> User | None:
        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id") or session.get("client_reference_id")
        if user_id is not None:
            try:
                return self.users.get(int(user_id))
            except (TypeError, ValueError):
                pass
        customer_id = session.get("customer")
        if isinstance(customer_id, str):
            return self.users.get_by_stripe_customer_id(customer_id)
        return None

    def _user_for_subscription(self, subscription: dict[str, Any]) -> User | None:
        metadata = subscription.get("metadata") or {}
        user_id = metadata.get("user_id")
        if user_id is not None:
            try:
                user = self.users.get(int(user_id))
                if user:
                    return user
            except (TypeError, ValueError):
                pass
        customer_id = subscription.get("customer")
        if isinstance(customer_id, str):
            return self.users.get_by_stripe_customer_id(customer_id)
        return None

    def _ensure_customer(self, user: User) -> str:
        if user.stripe_customer_id:
            return user.stripe_customer_id
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        self.users.update_billing(user, stripe_customer_id=customer.id)
        return customer.id

    def _require_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    def _require_billing_enabled(self) -> None:
        if not settings.billing_enabled:
            raise ValidationError("Billing is not configured on this server.")

    @staticmethod
    def _plan_id(plan: str) -> PlanId:
        if plan in VALID_PLANS:
            return plan  # type: ignore[return-value]
        return "free"
