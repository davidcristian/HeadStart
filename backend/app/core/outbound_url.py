"""Outbound URL policy for server-side HTTP fetches (scrapers, notifiers).

Blocks requests to private, loopback, link-local, and metadata addresses so
authenticated users cannot use the platform as an SSRF proxy.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from app.core.config import get_settings

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
    }
)
# Reserved TLDs that don't resolve on a compliant resolver (RFC 2606/6761). They
# are a DNS-free escape hatch for tests ONLY: in local/test the resolution + IP
# checks are skipped (see `_reserved_test_tld_bypass_allowed`), but production
# resolves them normally so a rogue / split-horizon resolver can't smuggle an
# internal address past the SSRF checks. `.localhost` is excluded entirely
# because it resolves to loopback and must always be checked.
_TEST_TLD_SUFFIXES = (".test", ".example", ".invalid")
_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})


class UnsafeOutboundUrlError(ValueError):
    """Raised when a URL targets a disallowed host or network."""


@dataclass(frozen=True)
class PinnedOutboundRequest:
    """A URL rewritten to a resolved IP plus the original Host header value."""

    request_url: str
    host_header: str


def assert_safe_outbound_url(url: str) -> None:
    """Reject URLs that resolve to non-public destinations."""
    pin_outbound_request(url)


def pin_outbound_request(url: str) -> PinnedOutboundRequest:
    """Resolve once, validate IPs, and return an IP-literal URL for the connect."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeOutboundUrlError("Only http and https URLs are allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeOutboundUrlError("URL is missing a hostname.")

    host = hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES:
        raise UnsafeOutboundUrlError(f"Hostname '{hostname}' is not allowed.")

    if _hostname_is_blocked_ip(host):
        raise UnsafeOutboundUrlError(f"Hostname '{hostname}' is not allowed.")

    if _reserved_test_tld_bypass_allowed() and host.endswith(_TEST_TLD_SUFFIXES):
        return PinnedOutboundRequest(request_url=url, host_header=host)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addrinfos = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise UnsafeOutboundUrlError(f"Unable to resolve hostname '{hostname}'.") from exc

    if not addrinfos:
        raise UnsafeOutboundUrlError(f"Unable to resolve hostname '{hostname}'.")

    chosen_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    for info in addrinfos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise UnsafeOutboundUrlError(f"Hostname '{hostname}' resolves to a disallowed address.")
        if chosen_ip is None:
            chosen_ip = ip

    assert chosen_ip is not None
    ip_literal = f"[{chosen_ip}]" if chosen_ip.version == 6 else str(chosen_ip)
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = f"{ip_literal}:{port}" if port != default_port else ip_literal
    pinned_url = urlunparse(parsed._replace(netloc=netloc))
    return PinnedOutboundRequest(request_url=pinned_url, host_header=host)


def _reserved_test_tld_bypass_allowed() -> bool:
    """Reserved test TLDs skip DNS only in local/test; prod resolves + IP-checks them."""
    return get_settings().environment.strip().lower() in _LOCAL_ENVIRONMENTS


def _hostname_is_blocked_ip(host: str) -> bool:
    try:
        return _is_blocked_ip(ipaddress.ip_address(host))
    except ValueError:
        return False


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )
