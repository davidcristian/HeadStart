"""Tests for the unauthenticated mailbox OAuth callback redirects."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.inbox import InboxService

_PROVIDERS = ["gmail", "outlook", "yahoo"]
_COMPLETE = {
    "gmail": "complete_gmail_oauth",
    "outlook": "complete_outlook_oauth",
    "yahoo": "complete_yahoo_oauth",
}


@pytest.fixture(autouse=True)
def _frontend_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "frontend_base_url", "https://app.example.test/")


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_callback_redirects_on_provider_error(client: TestClient, provider: str) -> None:
    resp = client.get(
        f"/api/v1/inbox/{provider}/callback?error=access_denied",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert f"mailbox={provider}_error" in location
    assert "reason=access_denied" in location


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_callback_redirects_when_code_missing(client: TestClient, provider: str) -> None:
    resp = client.get(
        f"/api/v1/inbox/{provider}/callback?state=abc",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "reason=missing_code" in resp.headers["location"]


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_callback_redirects_error_on_validation_failure(client: TestClient, provider: str) -> None:
    with patch.object(InboxService, _COMPLETE[provider], side_effect=ValidationError("bad")):
        resp = client.get(
            f"/api/v1/inbox/{provider}/callback?code=c&state=s",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert f"mailbox={provider}_error" in location
    assert "reason=" not in location  # generic error page, no reason query


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_callback_redirects_connected_on_success(client: TestClient, provider: str) -> None:
    with patch.object(InboxService, _COMPLETE[provider], return_value=None):
        resp = client.get(
            f"/api/v1/inbox/{provider}/callback?code=c&state=s",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert f"mailbox={provider}_connected" in resp.headers["location"]
