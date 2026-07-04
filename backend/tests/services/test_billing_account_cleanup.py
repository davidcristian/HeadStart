"""Unit tests for Stripe teardown on account deletion."""

from unittest.mock import MagicMock, patch

import pytest
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import DeleteAccountRequest, RegisterRequest
from app.services.auth import AuthService
from app.services.billing_account_cleanup import release_stripe_billing


@pytest.fixture
def stripe_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_cleanup")


def _user_with_billing(
    db_session: Session,
    *,
    email: str = "billed@example.com",
    subscription_id: str | None = "sub_test",
    customer_id: str | None = "cus_test",
) -> User:
    user = User(
        email=email,
        password_hash="hash",
        plan="pro",
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        subscription_status="active",
    )
    return UserRepository(db_session).add(user)


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_cancels_subscription_and_deletes_customer(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    stripe_secret: None,
) -> None:
    user = _user_with_billing(db_session)
    release_stripe_billing(user)
    mock_cancel.assert_called_once_with("sub_test")
    mock_delete.assert_called_once_with("cus_test")


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_skips_when_stripe_unconfigured(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    user = _user_with_billing(db_session)
    release_stripe_billing(user)
    mock_cancel.assert_not_called()
    mock_delete.assert_not_called()


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_subscription_only_when_no_customer(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    stripe_secret: None,
) -> None:
    user = _user_with_billing(db_session, customer_id=None)
    release_stripe_billing(user)
    mock_cancel.assert_called_once_with("sub_test")
    mock_delete.assert_not_called()


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_customer_only_when_no_subscription(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    stripe_secret: None,
) -> None:
    user = _user_with_billing(db_session, subscription_id=None)
    release_stripe_billing(user)
    mock_cancel.assert_not_called()
    mock_delete.assert_called_once_with("cus_test")


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_swallows_stripe_errors(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    stripe_secret: None,
) -> None:
    user = _user_with_billing(db_session)
    mock_cancel.side_effect = stripe.InvalidRequestError(
        message="No such subscription",
        param="id",
        code="resource_missing",
    )
    mock_delete.side_effect = stripe.StripeError("network down")
    release_stripe_billing(user)  # must not raise
    mock_cancel.assert_called_once()
    mock_delete.assert_called_once()


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_swallows_subscription_stripe_error(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    stripe_secret: None,
) -> None:
    user = _user_with_billing(db_session)
    mock_cancel.side_effect = stripe.StripeError("timeout")
    release_stripe_billing(user)
    mock_cancel.assert_called_once()
    mock_delete.assert_called_once_with("cus_test")


@patch("app.services.billing_account_cleanup.stripe.Customer.delete")
@patch("app.services.billing_account_cleanup.stripe.Subscription.cancel")
def test_release_swallows_customer_invalid_request(
    mock_cancel: MagicMock,
    mock_delete: MagicMock,
    db_session: Session,
    stripe_secret: None,
) -> None:
    user = _user_with_billing(db_session, subscription_id=None)
    mock_delete.side_effect = stripe.InvalidRequestError(
        message="No such customer",
        param="id",
        code="resource_missing",
    )
    release_stripe_billing(user)
    mock_delete.assert_called_once()


@patch("app.services.auth_account.release_stripe_billing")
def test_delete_account_releases_stripe_before_local_delete(
    mock_release: MagicMock,
    db_session: Session,
) -> None:
    service = AuthService(db_session)
    user = service.register(
        RegisterRequest(email="stripe-delete@example.com", password="password123")
    )
    UserRepository(db_session).update_billing(
        user,
        stripe_customer_id="cus_del",
        stripe_subscription_id="sub_del",
        subscription_status="active",
        plan="pro",
    )
    service.delete_account(user.id, DeleteAccountRequest(password="password123"))
    mock_release.assert_called_once()
    released = mock_release.call_args.args[0]
    assert released.stripe_customer_id == "cus_del"
    assert released.stripe_subscription_id == "sub_del"
    assert UserRepository(db_session).get(user.id) is None
