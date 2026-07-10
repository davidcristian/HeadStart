"""Tests for LinkedIn/Indeed private-API risk acknowledgment (APL-17)."""

from __future__ import annotations

from app.appliers.private_api_risk import (
    ACCEPT_PRIVATE_API_RISK_KEY,
    PRIVATE_API_RISK_ADAPTERS,
    config_accepts_private_api_risk,
    private_api_risk_rejection_error,
    requires_private_api_risk_ack,
)


def test_requires_ack_only_for_linkedin_and_indeed() -> None:
    assert frozenset({"linkedin", "indeed"}) == PRIVATE_API_RISK_ADAPTERS
    assert requires_private_api_risk_ack("linkedin") is True
    assert requires_private_api_risk_ack("indeed") is True
    assert requires_private_api_risk_ack("greenhouse") is False


def test_config_accepts_private_api_risk() -> None:
    assert config_accepts_private_api_risk(None) is False
    assert config_accepts_private_api_risk({}) is False
    assert config_accepts_private_api_risk({ACCEPT_PRIVATE_API_RISK_KEY: False}) is False
    assert config_accepts_private_api_risk({ACCEPT_PRIVATE_API_RISK_KEY: True}) is True
    assert config_accepts_private_api_risk({ACCEPT_PRIVATE_API_RISK_KEY: "yes"}) is True


def test_rejection_error_mentions_tos_and_config_key() -> None:
    message = private_api_risk_rejection_error()
    assert "Terms of Service" in message
    assert ACCEPT_PRIVATE_API_RISK_KEY in message
    assert "Voyager" in message
    assert "smartapply" in message
