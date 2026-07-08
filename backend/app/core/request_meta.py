"""Helpers for extracting client metadata from HTTP requests."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from starlette.requests import Request

from app.core.config import settings

# data_request_log.ip_address is String(45); reject longer raw tokens before parse.
_MAX_IP_LEN = 45


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip_address: str | None
    user_agent: str | None


def request_meta(request: Request) -> RequestMeta:
    """Best-effort client IP and user agent for audit logging (AUT-17)."""
    return RequestMeta(ip_address=_client_ip(request), user_agent=request.headers.get("user-agent"))


def _client_ip(request: Request) -> str | None:
    """Resolve client IP; honor XFF only from configured trusted proxy peers."""
    peer = _normalize_ip(request.client.host if request.client is not None else None)
    trusted = _trusted_networks()
    if not trusted or peer is None or not _ip_in_networks(peer, trusted):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer

    # XFF order is client, proxy1, …; walk right→left past trusted hops.
    for hop in reversed([part.strip() for part in forwarded.split(",") if part.strip()]):
        candidate = _normalize_ip(hop)
        if candidate is None:
            continue
        if _ip_in_networks(candidate, trusted):
            continue
        return candidate
    return peer


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse configured TRUSTED_PROXY_CIDRS (invalid entries already rejected at boot)."""
    return [ipaddress.ip_network(cidr, strict=False) for cidr in settings.trusted_proxy_cidrs]


def _ip_in_networks(
    ip_text: str,
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    """Return True when *ip_text* (already normalized) falls inside any trusted CIDR."""
    addr = ipaddress.ip_address(ip_text)
    return any(addr in network for network in networks)


def _normalize_ip(raw: str | None) -> str | None:
    """Parse and canonicalize an IP; drop invalid or overlong values (AUT-17)."""
    if raw is None:
        return None
    text = raw.strip()
    if not text or len(text) > _MAX_IP_LEN:
        return None
    if text.startswith("[") and "]" in text:
        text = text[1 : text.index("]")]
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None
