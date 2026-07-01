"""Billing API and webhook tests."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.repositories.users import UserRepository
from tests.conftest import register_and_login


@pytest.fixture
def billing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_billing")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_billing")
    monkeypatch.setattr(settings, "stripe_price_pro_monthly", "price_pro_monthly")
    monkeypatch.setattr(settings, "stripe_price_pro_annual", "price_pro_annual")
    monkeypatch.setattr(settings, "stripe_trial_days", 14)


def _patch_user_billing(user_id: int, **fields: object) -> None:
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    try:
        user = UserRepository(db).get(user_id)
        assert user is not None
        UserRepository(db).update_billing(user, **fields)  # type: ignore[arg-type]
        db.commit()
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


def test_billing_status_unconfigured(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/billing/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["plan"] == "free"
    assert body["can_checkout"] is False


def test_billing_status_configured(
    client: TestClient, auth_headers: dict[str, str], billing_settings: None
) -> None:
    resp = client.get("/api/v1/billing/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["can_checkout"] is True
    assert body["trial_days"] == 14


@patch("app.services.billing.stripe.checkout.Session.create")
@patch("app.services.billing.stripe.Customer.create")
def test_create_checkout_session(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    client: TestClient,
    auth_headers: dict[str, str],
    billing_settings: None,
) -> None:
    mock_customer_create.return_value = MagicMock(id="cus_test_1")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.test/session")

    resp = client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "pro", "billing_period": "annual"},
    )
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.test/session"
    mock_session_create.assert_called_once()
    call_kwargs = mock_session_create.call_args.kwargs
    assert call_kwargs["line_items"] == [{"price": "price_pro_annual", "quantity": 1}]
    assert call_kwargs["subscription_data"]["trial_period_days"] == 14


@patch("app.services.billing.stripe.billing_portal.Session.create")
def test_create_portal_requires_customer(
    mock_portal_create: MagicMock,
    client: TestClient,
    auth_headers: dict[str, str],
    billing_settings: None,
) -> None:
    resp = client.post("/api/v1/billing/portal", headers=auth_headers, json={})
    assert resp.status_code == 400
    assert "billing account" in resp.json()["detail"].lower()
    mock_portal_create.assert_not_called()


@patch("app.services.billing.stripe.billing_portal.Session.create")
def test_create_portal_session(
    mock_portal_create: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="billing@example.com", password="password123")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    _patch_user_billing(me["id"], stripe_customer_id="cus_existing")

    mock_portal_create.return_value = MagicMock(url="https://billing.stripe.test/portal")
    resp = client.post("/api/v1/billing/portal", headers=headers, json={})
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://billing.stripe.test/portal"


@patch("app.services.billing.stripe.Webhook.construct_event")
def test_webhook_updates_subscription(
    mock_construct: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="webhook@example.com", password="password123")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    _patch_user_billing(
        me["id"],
        stripe_customer_id="cus_webhook",
        stripe_subscription_id="sub_webhook",
    )

    mock_construct.return_value = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_webhook",
                "customer": "cus_webhook",
                "status": "active",
                "metadata": {"user_id": str(me["id"]), "plan": "pro"},
                "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
            }
        },
    }

    resp = client.post(
        "/api/v1/billing/webhook",
        data=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    assert resp.status_code == 204

    refreshed = client.get("/api/v1/auth/me", headers=headers).json()
    assert refreshed["plan"] == "pro"


@patch("app.services.billing.stripe.Webhook.construct_event")
def test_webhook_downgrades_on_cancel(
    mock_construct: MagicMock,
    client: TestClient,
    billing_settings: None,
) -> None:
    headers = register_and_login(client, email="cancel@example.com", password="password123")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    _patch_user_billing(
        me["id"],
        stripe_customer_id="cus_cancel",
        stripe_subscription_id="sub_cancel",
        subscription_status="active",
        plan="pro",
    )

    mock_construct.return_value = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_cancel",
                "customer": "cus_cancel",
                "status": "canceled",
                "metadata": {"user_id": str(me["id"])},
                "items": {"data": []},
            }
        },
    }

    resp = client.post(
        "/api/v1/billing/webhook",
        data=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    assert resp.status_code == 204

    refreshed = client.get("/api/v1/auth/me", headers=headers).json()
    assert refreshed["plan"] == "free"
