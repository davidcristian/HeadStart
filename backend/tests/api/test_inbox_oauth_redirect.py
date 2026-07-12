"""Unit tests for mailbox OAuth Settings redirect helper."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from app.api.v1.inbox_oauth_redirect import mailbox_oauth_settings_redirect
from app.core.config import settings


def test_mailbox_oauth_settings_redirect_encodes_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_base_url", "https://app.example.test/")
    reason = "denied&x=1#frag"
    resp = mailbox_oauth_settings_redirect("gmail_error", reason=reason)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://app.example.test/app/settings?")
    assert "&x=1" not in location
    assert "#frag" not in location
    assert parse_qs(urlparse(location).query) == {
        "mailbox": ["gmail_error"],
        "reason": [reason],
    }


def test_mailbox_oauth_settings_redirect_omits_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_base_url", "https://app.example.test/")
    resp = mailbox_oauth_settings_redirect("gmail_connected")
    assert parse_qs(urlparse(resp.headers["location"]).query) == {
        "mailbox": ["gmail_connected"],
    }
