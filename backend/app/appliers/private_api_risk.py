"""Opt-in acknowledgment for LinkedIn/Indeed private-API live apply."""

from __future__ import annotations

from typing import Any

# Hosted Easy Apply posts to Voyager / smartapply with the candidate's session
# cookies. These private APIs can trip ToS/anti-automation and ban personal
# accounts.
PRIVATE_API_RISK_ADAPTERS = frozenset({"linkedin", "indeed"})
ACCEPT_PRIVATE_API_RISK_KEY = "accept_private_api_risk"

_PRIVATE_API_RISK_ERROR = (
    "LinkedIn/Indeed hosted Easy Apply uses private APIs (Voyager / smartapply) with "
    "your session cookies; automated use can violate their Terms of Service and risk "
    "account suspension or bans. Set config.accept_private_api_risk=true to acknowledge "
    "this risk before enabling auto-apply or live submit."
)


def requires_private_api_risk_ack(adapter_key: str) -> bool:
    """True when live cookie-driven submit for this adapter needs an explicit risk ack."""
    return adapter_key in PRIVATE_API_RISK_ADAPTERS


def config_accepts_private_api_risk(config: dict[str, Any] | None) -> bool:
    """True when source/search config explicitly acknowledges private-API / ban risk."""
    if not config:
        return False
    return bool(config.get(ACCEPT_PRIVATE_API_RISK_KEY))


def private_api_risk_rejection_error() -> str:
    """User-facing error when live LinkedIn/Indeed submit lacks the risk acknowledgment."""
    return _PRIVATE_API_RISK_ERROR
