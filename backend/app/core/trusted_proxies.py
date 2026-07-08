"""CSV list and TRUSTED_PROXY_CIDRS settings helpers (AUT-17)."""

from __future__ import annotations

import ipaddress
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator
from pydantic_settings import NoDecode


def parse_csv_list(value: object) -> object:
    """Split a comma-separated env string into a list; pass other types through."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def validate_trusted_proxy_cidrs(value: list[str]) -> list[str]:
    """Reject non-CIDR entries so misconfigured TRUSTED_PROXY_CIDRS fail at boot."""
    for cidr in value:
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError(f"TRUSTED_PROXY_CIDRS entry is not a valid CIDR: {cidr!r}") from exc
    return value


def normalize_samesite(value: object) -> object:
    """SameSite is case-insensitive; Starlette expects a lowercase literal."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


CsvStrList = Annotated[list[str], NoDecode, BeforeValidator(parse_csv_list)]
TrustedProxyCidrs = Annotated[
    list[str],
    NoDecode,
    BeforeValidator(parse_csv_list),
    AfterValidator(validate_trusted_proxy_cidrs),
]
