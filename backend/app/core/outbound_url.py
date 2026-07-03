"""Outbound URL policy for server-side HTTP fetches (scrapers, notifiers).

Blocks requests to private, loopback, link-local, and metadata addresses so
authenticated users cannot use the platform as an SSRF proxy.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

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
# internal address past the SSRF checks. `.localhost` is excluded entirely — it
# resolves to loopback and must always be checked.
_TEST_TLD_SUFFIXES = (".test", ".example", ".invalid")
_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})


class UnsafeOutboundUrlError(ValueError):
    """Raised when a URL targets a disallowed host or network."""


def assert_safe_outbound_url(url: str) -> None:
    """Reject URLs that resolve to non-public destinations."""
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
        return

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

    for info in addrinfos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise UnsafeOutboundUrlError(f"Hostname '{hostname}' resolves to a disallowed address.")


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
