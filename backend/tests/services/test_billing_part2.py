"""Billing service unit tests (webhook dispatch and resolution helpers)."""

from unittest.mock import MagicMock, patch

import pytest
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.promo_code import PromoCode
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from app.services.billing import BillingService


@pytest.fixture
def billing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_unit")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_unit")
    monkeypatch.setattr(settings, "stripe_price_starter_monthly", "price_starter_monthly")
    monkeypatch.setattr(settings, "stripe_price_starter_annual", "price_starter_annual")
    monkeypatch.setattr(settings, "stripe_price_plus_monthly", "price_plus_monthly")
    monkeypatch.setattr(settings, "stripe_price_plus_annual", "price_plus_annual")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_annual", "price_pro_annual")


def _add_user(db_session: Session, email: str = "billing-user@example.com") -> User:
    user = User(email=email, password_hash="hash", plan="free")
    return UserRepository(db_session).add(user)


# --- webhook dispatch -----------------------------------------------------


def test_webhook_requires_billing_enabled(db_session: Session) -> None:
    with pytest.raises(ValidationError, match="not configured"):
        BillingService(db_session).handle_webhook(b"{}", "sig")


def test_webhook_missing_signature(db_session: Session, billing_settings: None) -> None:
    with pytest.raises(ValidationError, match="Missing Stripe-Signature"):
        BillingService(db_session).handle_webhook(b"{}", None)


@patch("app.services.billing.stripe.Webhook.construct_event", side_effect=ValueError("bad"))
def test_webhook_invalid_payload(
    _mock: MagicMock, db_session: Session, billing_settings: None
) -> None:
    with pytest.raises(ValidationError, match="Invalid webhook payload"):
        BillingService(db_session).handle_webhook(b"{}", "sig")


@patch(
    "app.services.billing.stripe.Webhook.construct_event",
    side_effect=stripe.SignatureVerificationError("nope", "sig"),
)
def test_webhook_invalid_signature(
    _mock: MagicMock, db_session: Session, billing_settings: None
) -> None:
    with pytest.raises(ValidationError, match="Invalid webhook signature"):
        BillingService(db_session).handle_webhook(b"{}", "sig")


@patch("app.services.billing.stripe.Webhook.construct_event")
def test_webhook_ignores_unknown_event_type(
    mock_construct: MagicMock, db_session: Session, billing_settings: None
) -> None:
    mock_construct.return_value = {"type": "invoice.paid", "data": {"object": {}}}
    BillingService(db_session).handle_webhook(b"{}", "sig")


@patch("app.services.billing.stripe.Webhook.construct_event")
def test_webhook_checkout_completed_records_promo(
    mock_construct: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    promo = PromoCodeRepository(db_session).add(
        PromoCode(code="WELCOME", promo_type="percent_off", value_int=10)
    )
    mock_construct.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test",
                "client_reference_id": str(user.id),
                "customer": "cus_new",
                "subscription": "sub_new",
                "metadata": {"user_id": str(user.id), "promo_code_id": str(promo.id)},
            }
        },
    }
    BillingService(db_session).handle_webhook(b"{}", "sig")
    db_session.refresh(user)
    assert user.stripe_customer_id == "cus_new"
    assert user.stripe_subscription_id == "sub_new"
    assert PromoCodeRepository(db_session).count_user_redemptions(promo.id, user.id) == 1


def test_on_checkout_completed_without_user_is_noop(
    db_session: Session, billing_settings: None
) -> None:
    BillingService(db_session)._on_checkout_completed({"metadata": {}})


def test_on_checkout_completed_without_promo_metadata(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    service = BillingService(db_session)
    service._on_checkout_completed(
        {
            "id": "cs_nopromo",
            "client_reference_id": str(user.id),
            "customer": "cus_nopromo",
            "subscription": "sub_nopromo",
            "metadata": {"user_id": str(user.id)},
        }
    )
    db_session.refresh(user)
    assert user.stripe_customer_id == "cus_nopromo"


def test_on_checkout_completed_bad_promo_id_ignored(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    service = BillingService(db_session)
    service._on_checkout_completed(
        {
            "id": "cs_x",
            "client_reference_id": str(user.id),
            "metadata": {"user_id": str(user.id), "promo_code_id": "not-an-int"},
        }
    )
    db_session.refresh(user)
    assert user.stripe_customer_id is None


def test_on_checkout_completed_unknown_promo_id_ignored(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    service = BillingService(db_session)
    service._on_checkout_completed(
        {
            "id": "cs_y",
            "client_reference_id": str(user.id),
            "metadata": {"user_id": str(user.id), "promo_code_id": "424242"},
        }
    )
    db_session.refresh(user)
    assert user.stripe_customer_id is None


# --- subscription update / delete branches --------------------------------


def test_on_subscription_updated_unknown_user_is_noop(
    db_session: Session, billing_settings: None
) -> None:
    BillingService(db_session)._on_subscription_updated(
        {"id": "sub_ghost", "customer": "cus_ghost", "status": "active", "metadata": {}}
    )


def test_on_subscription_deleted_unknown_user_is_noop(
    db_session: Session, billing_settings: None
) -> None:
    BillingService(db_session)._on_subscription_deleted(
        {"id": "sub_ghost", "customer": "cus_ghost", "metadata": {}}
    )


def test_plan_from_subscription_inactive_status_is_free(
    db_session: Session, billing_settings: None
) -> None:
    service = BillingService(db_session)
    assert (
        service._plan_from_subscription({"status": "canceled", "metadata": {}}, "canceled")
        == "free"
    )


def test_plan_from_subscription_non_string_price_falls_through_to_metadata(
    db_session: Session, billing_settings: None
) -> None:
    service = BillingService(db_session)
    plan = service._plan_from_subscription(
        {
            "id": "sub_np",
            "status": "active",
            "metadata": {"plan": "plus"},
            "items": {"data": [{"price": {"id": 12345}}]},
        },
        "active",
    )
    assert plan == "plus"


# --- user resolution helpers ----------------------------------------------


def test_user_from_reference_bad_user_id_uses_customer(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_ref")
    service = BillingService(db_session)
    resolved = service._user_from_reference(
        {"metadata": {"user_id": "not-int"}, "customer": "cus_ref"}
    )
    assert resolved is not None and resolved.id == user.id


def test_user_from_reference_no_identifiers_returns_none(
    db_session: Session, billing_settings: None
) -> None:
    assert BillingService(db_session)._user_from_reference({"metadata": {}}) is None


def test_user_for_subscription_metadata_hit(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    service = BillingService(db_session)
    resolved = service._user_for_subscription({"metadata": {"user_id": str(user.id)}})
    assert resolved is not None and resolved.id == user.id


def test_user_for_subscription_valid_but_missing_user_falls_back_to_customer(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_fallback")
    service = BillingService(db_session)
    # user_id parses to an int but no such user exists -> falls through to
    # the customer lookup.
    resolved = service._user_for_subscription(
        {"metadata": {"user_id": "987654"}, "customer": "cus_fallback"}
    )
    assert resolved is not None and resolved.id == user.id


def test_user_for_subscription_bad_metadata_uses_customer(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_sub")
    service = BillingService(db_session)
    resolved = service._user_for_subscription(
        {"metadata": {"user_id": "nope"}, "customer": "cus_sub"}
    )
    assert resolved is not None and resolved.id == user.id


def test_user_for_subscription_no_identifiers_returns_none(
    db_session: Session, billing_settings: None
) -> None:
    assert BillingService(db_session)._user_for_subscription({"metadata": {}}) is None


def test_ensure_customer_reuses_existing_id(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_keep")
    assert BillingService(db_session)._ensure_customer(user) == "cus_keep"


@patch("app.services.billing.stripe.billing_portal.Session.create")
def test_portal_raises_when_no_url(
    mock_portal_create: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_portal")
    mock_portal_create.return_value = MagicMock(url=None)
    with pytest.raises(ValidationError, match="did not return a portal URL"):
        BillingService(db_session).create_portal_session(user.id)


@patch("app.services.billing.stripe.billing_portal.Session.create")
def test_portal_returns_url(
    mock_portal_create: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_portal2")
    mock_portal_create.return_value = MagicMock(url="https://billing.test/portal")
    assert (
        BillingService(db_session).create_portal_session(user.id) == "https://billing.test/portal"
    )
