"""Billing service unit tests."""

from unittest.mock import MagicMock, patch

import pytest
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
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


def test_status_for_free_user(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    status = BillingService(db_session).status(user.id)
    assert status.configured is True
    assert status.plan == "free"
    assert status.can_checkout is True


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_create_checkout_creates_customer(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    user = _add_user(db_session)
    mock_customer_create.return_value = MagicMock(id="cus_new")
    mock_session_create.return_value = MagicMock(url="https://checkout.test/url")

    url = BillingService(db_session).create_checkout_session(
        user.id, plan="pro", billing_period="monthly"
    )
    assert url == "https://checkout.test/url"
    db_session.refresh(user)
    assert user.stripe_customer_id == "cus_new"


def test_plan_from_subscription_price_mapping(db_session: Session, billing_settings: None) -> None:
    service = BillingService(db_session)
    assert (
        service._plan_from_subscription(
            {
                "status": "active",
                "metadata": {},
                "items": {"data": [{"price": {"id": "price_starter_annual"}}]},
            },
            "active",
        )
        == "starter"
    )
    plan = service._plan_from_subscription(
        {
            "status": "active",
            "metadata": {},
            "items": {"data": [{"price": {"id": "price_pro_annual"}}]},
        },
        "active",
    )
    assert plan == "pro"


def test_unknown_subscription_price_defaults_to_lowest_paid_tier(
    db_session: Session, billing_settings: None
) -> None:
    """Regression: an unmappable price must not silently grant Pro for free."""
    service = BillingService(db_session)
    plan = service._plan_from_subscription(
        {
            "id": "sub_unknown",
            "status": "active",
            "metadata": {},
            "items": {"data": [{"price": {"id": "price_not_configured"}}]},
        },
        "active",
    )
    assert plan == "starter"


def test_subscription_without_items_falls_back_to_metadata_plan(
    db_session: Session, billing_settings: None
) -> None:
    service = BillingService(db_session)
    plan = service._plan_from_subscription(
        {"id": "sub_meta", "status": "active", "metadata": {"plan": "plus"}, "items": {"data": []}},
        "active",
    )
    assert plan == "plus"


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_plan_upgrade_promo_bills_target_plan_price(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    db_session: Session,
    billing_settings: None,
) -> None:
    """A plan_upgrade promo must charge (and grant) the target plan, not the requested one."""
    user = _add_user(db_session)
    PromoCodeRepository(db_session).add(
        PromoCode(
            code="UPGRADE",
            promo_type="plan_upgrade",
            value_int=1,
            plan_target="pro",
            stripe_coupon_id="coupon_upgrade",
            stripe_promotion_code_id="promo_upgrade",
        )
    )
    mock_customer_create.return_value = MagicMock(id="cus_upgrade")
    mock_session_create.return_value = MagicMock(url="https://checkout.test/upgrade")

    BillingService(db_session).create_checkout_session(
        user.id, plan="starter", billing_period="monthly", promo_code="UPGRADE"
    )
    kwargs = mock_session_create.call_args.kwargs
    assert kwargs["line_items"] == [{"price": "price_pro_monthly", "quantity": 1}]
    assert kwargs["metadata"]["plan"] == "pro"
    assert kwargs["subscription_data"]["metadata"]["plan"] == "pro"
    assert kwargs["discounts"] == [{"promotion_code": "promo_upgrade"}]


# --- status / plan mapping ------------------------------------------------


def test_status_with_active_subscription_cannot_checkout(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_x",
        stripe_subscription_id="sub_x",
        subscription_status="active",
        plan="pro",
    )
    status = BillingService(db_session).status(user.id)
    assert status.can_checkout is False
    assert status.can_manage is True
    assert status.has_stripe_subscription is True


def test_plan_id_falls_back_to_free_for_unknown(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    user.plan = "legacy"
    db_session.flush()
    status = BillingService(db_session).status(user.id)
    assert status.plan == "free"


def test_status_missing_user_raises(db_session: Session, billing_settings: None) -> None:
    with pytest.raises(NotFoundError):
        BillingService(db_session).status(999999)


# --- checkout guards ------------------------------------------------------


def test_checkout_requires_billing_enabled(db_session: Session) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not configured"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="pro", billing_period="monthly"
        )


def test_checkout_rejects_invalid_plan(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="Invalid checkout plan"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="ultra", billing_period="monthly"
        )


def test_checkout_rejects_when_already_subscribed(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, subscription_status="active")
    with pytest.raises(ValidationError, match="already have an active subscription"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="pro", billing_period="monthly"
        )


def test_checkout_unsupported_period_raises(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not fully configured"):
        BillingService(db_session).create_checkout_session(
            user.id,
            plan="pro",
            billing_period="weekly",  # type: ignore[arg-type]
        )


@patch("app.services.billing.price_id_for", return_value="")
def test_checkout_missing_price_raises(
    _mock_price: MagicMock, db_session: Session, billing_settings: None
) -> None:
    # billing_enabled requires every price to be set, so an empty resolved price
    # is only reachable by forcing price_id_for to return "".
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not fully configured"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="pro", billing_period="monthly"
        )


@patch("app.services.billing.stripe.checkout.Session.create")
def test_checkout_free_trial_promo_sets_trial(
    mock_session_create: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_trial")
    PromoCodeRepository(db_session).add(
        PromoCode(code="FREE30", promo_type="free_trial_days", value_int=30)
    )
    mock_session_create.return_value = MagicMock(url="https://checkout.test/trial")

    BillingService(db_session).create_checkout_session(
        user.id, plan="starter", billing_period="monthly", promo_code="FREE30"
    )
    kwargs = mock_session_create.call_args.kwargs
    assert kwargs["subscription_data"]["trial_period_days"] == 30
    assert "discounts" not in kwargs


@patch("app.services.billing.stripe.checkout.Session.create")
def test_checkout_raises_when_stripe_returns_no_url(
    mock_session_create: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(user, stripe_customer_id="cus_nourl")
    mock_session_create.return_value = MagicMock(url=None)
    with pytest.raises(ValidationError, match="did not return a checkout URL"):
        BillingService(db_session).create_checkout_session(
            user.id, plan="starter", billing_period="monthly"
        )


def test_create_checkout_missing_user_raises(db_session: Session, billing_settings: None) -> None:
    with pytest.raises(NotFoundError):
        BillingService(db_session).create_checkout_session(
            999999, plan="pro", billing_period="monthly"
        )


# --- portal ---------------------------------------------------------------


def test_portal_requires_billing_enabled(db_session: Session) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="not configured"):
        BillingService(db_session).create_portal_session(user.id)


def test_portal_requires_customer(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    with pytest.raises(ValidationError, match="No billing account"):
        BillingService(db_session).create_portal_session(user.id)


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
    control = _add_user(db_session, email="control-checkout@example.com")
    UserRepository(db_session).update_billing(
        control,
        stripe_customer_id="cus_control",
        stripe_subscription_id="sub_control",
        subscription_status="active",
        plan="starter",
    )
    db_session.flush()

    BillingService(db_session)._on_checkout_completed({"metadata": {}})

    db_session.refresh(control)
    assert control.stripe_customer_id == "cus_control"
    assert control.stripe_subscription_id == "sub_control"
    assert control.plan == "starter"


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
    control = _add_user(db_session, email="control-updated@example.com")
    UserRepository(db_session).update_billing(
        control,
        stripe_customer_id="cus_real",
        stripe_subscription_id="sub_real",
        subscription_status="active",
        plan="pro",
    )
    db_session.flush()

    BillingService(db_session)._on_subscription_updated(
        {"id": "sub_ghost", "customer": "cus_ghost", "status": "active", "metadata": {}}
    )

    db_session.refresh(control)
    assert control.stripe_customer_id == "cus_real"
    assert control.stripe_subscription_id == "sub_real"
    assert control.plan == "pro"
    assert control.subscription_status == "active"


def test_on_subscription_deleted_unknown_user_is_noop(
    db_session: Session, billing_settings: None
) -> None:
    control = _add_user(db_session, email="control-deleted@example.com")
    UserRepository(db_session).update_billing(
        control,
        stripe_customer_id="cus_keep",
        stripe_subscription_id="sub_keep",
        subscription_status="active",
        plan="plus",
    )
    db_session.flush()

    BillingService(db_session)._on_subscription_deleted(
        {"id": "sub_ghost", "customer": "cus_ghost", "metadata": {}}
    )

    db_session.refresh(control)
    assert control.stripe_customer_id == "cus_keep"
    assert control.stripe_subscription_id == "sub_keep"
    assert control.plan == "plus"
    assert control.subscription_status == "active"


def test_subscription_deleted_clears_id_and_downgrades(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_del",
        stripe_subscription_id="sub_del",
        subscription_status="active",
        plan="pro",
    )
    BillingService(db_session)._on_subscription_deleted(
        {
            "id": "sub_del",
            "customer": "cus_del",
            "metadata": {"user_id": str(user.id)},
        },
        event_at=1_700_000_100,
    )
    db_session.refresh(user)
    assert user.stripe_subscription_id is None
    assert user.subscription_status == "canceled"
    assert user.plan == "free"
    assert user.stripe_billing_event_at == 1_700_000_100


def test_stale_subscription_updated_after_delete_does_not_regrant(
    db_session: Session, billing_settings: None
) -> None:
    """BIL-02: a delayed updated must not revive a plan after deleted."""
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_stale",
        stripe_subscription_id="sub_stale",
        subscription_status="active",
        plan="pro",
    )
    service = BillingService(db_session)
    service._on_subscription_deleted(
        {
            "id": "sub_stale",
            "customer": "cus_stale",
            "metadata": {"user_id": str(user.id)},
        },
        event_at=1_700_000_200,
    )
    service._on_subscription_updated(
        {
            "id": "sub_stale",
            "customer": "cus_stale",
            "status": "active",
            "metadata": {"user_id": str(user.id), "plan": "pro"},
            "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
        },
        event_at=1_700_000_150,
    )
    db_session.refresh(user)
    assert user.plan == "free"
    assert user.subscription_status == "canceled"
    assert user.stripe_subscription_id is None
    assert user.stripe_billing_event_at == 1_700_000_200


def test_deleted_for_superseded_subscription_does_not_wipe_current(
    db_session: Session, billing_settings: None
) -> None:
    """BIL-03: late deleted for an old sub must not downgrade a newer one."""
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_new",
        stripe_subscription_id="sub_new",
        subscription_status="active",
        plan="plus",
        stripe_billing_event_at=1_700_000_300,
    )
    BillingService(db_session)._on_subscription_deleted(
        {
            "id": "sub_old",
            "customer": "cus_new",
            "metadata": {"user_id": str(user.id)},
        },
        event_at=1_700_000_250,
    )
    db_session.refresh(user)
    assert user.stripe_subscription_id == "sub_new"
    assert user.plan == "plus"
    assert user.subscription_status == "active"
    assert user.stripe_billing_event_at == 1_700_000_300


def test_updated_for_superseded_subscription_is_ignored(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_cur",
        stripe_subscription_id="sub_cur",
        subscription_status="active",
        plan="starter",
        stripe_billing_event_at=1_700_000_400,
    )
    BillingService(db_session)._on_subscription_updated(
        {
            "id": "sub_old",
            "customer": "cus_cur",
            "status": "active",
            "metadata": {"user_id": str(user.id), "plan": "pro"},
            "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
        },
        event_at=1_700_000_450,
    )
    db_session.refresh(user)
    assert user.stripe_subscription_id == "sub_cur"
    assert user.plan == "starter"


def test_stale_subscription_deleted_is_ignored(db_session: Session, billing_settings: None) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_stale_del",
        stripe_subscription_id="sub_stale_del",
        subscription_status="active",
        plan="pro",
        stripe_billing_event_at=1_700_000_600,
    )
    BillingService(db_session)._on_subscription_deleted(
        {
            "id": "sub_stale_del",
            "customer": "cus_stale_del",
            "metadata": {"user_id": str(user.id)},
        },
        event_at=1_700_000_500,
    )
    db_session.refresh(user)
    assert user.plan == "pro"
    assert user.stripe_subscription_id == "sub_stale_del"
    assert user.subscription_status == "active"


def test_unsigned_subscription_updated_ignored_after_watermark(
    db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_unsigned",
        stripe_subscription_id="sub_unsigned",
        subscription_status="canceled",
        plan="free",
        stripe_billing_event_at=1_700_000_700,
    )
    BillingService(db_session)._on_subscription_updated(
        {
            "id": "sub_unsigned",
            "customer": "cus_unsigned",
            "status": "active",
            "metadata": {"user_id": str(user.id), "plan": "pro"},
            "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
        },
    )
    db_session.refresh(user)
    assert user.plan == "free"
    assert user.subscription_status == "canceled"


@patch("app.services.billing.stripe.Webhook.construct_event")
def test_webhook_passes_event_created_into_subscription_handlers(
    mock_construct: MagicMock, db_session: Session, billing_settings: None
) -> None:
    user = _add_user(db_session)
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_wh",
        stripe_subscription_id="sub_wh",
    )
    mock_construct.return_value = {
        "type": "customer.subscription.updated",
        "created": 1_700_000_500,
        "data": {
            "object": {
                "id": "sub_wh",
                "customer": "cus_wh",
                "status": "active",
                "metadata": {"user_id": str(user.id), "plan": "pro"},
                "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
            }
        },
    }
    BillingService(db_session).handle_webhook(b"{}", "sig")
    db_session.refresh(user)
    assert user.plan == "pro"
    assert user.stripe_billing_event_at == 1_700_000_500


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
