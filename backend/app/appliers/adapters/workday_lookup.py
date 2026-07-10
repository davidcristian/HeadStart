"""Shared Workday CXS lookup helpers for institution value resolution."""

from __future__ import annotations

import re
from typing import Any

_WORKDAY_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_LOOKUP_LIST_KEYS = ("data", "items", "values", "results")


def is_workday_id(value: str) -> bool:
    """Return whether a string looks like a Workday WID."""
    return bool(_WORKDAY_ID_RE.match(value.strip()))


def normalize_lookup_text(value: str) -> str:
    """Normalize free text for exact institution-value matching."""
    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", "", lowered)


def parse_lookup_items(data: Any) -> list[dict[str, str]]:
    """Extract id/descriptor rows from a Workday institution-values response."""
    if isinstance(data, list):
        return _parse_lookup_rows(data)
    if not isinstance(data, dict):
        return []

    for key in _LOOKUP_LIST_KEYS:
        rows = data.get(key)
        if isinstance(rows, list):
            return _parse_lookup_rows(rows)
    return []


def match_lookup_item(items: list[dict[str, str]], value: str) -> dict[str, str] | None:
    """Pick the catalog row that exactly (or normalized-equal) matches a profile value.

    A supplied Workday WID is accepted only when it appears in ``items`` (APL-24);
    out-of-catalog hex ids return None so callers fall back to a self-reported
    descriptor. Prefix/substring fallbacks are intentionally omitted: short or
    common labels (e.g. ``BS``, ``Java``) otherwise bind a longer unrelated
    catalog WID.
    """
    stripped = value.strip()
    if not stripped:
        return None
    if is_workday_id(stripped):
        for item in items:
            if item.get("id", "").lower() == stripped.lower():
                return item
        return None

    target = stripped.lower()
    normalized_target = normalize_lookup_text(stripped)

    for item in items:
        descriptor = item.get("descriptor", "")
        if descriptor.lower() == target:
            return item

    for item in items:
        descriptor = item.get("descriptor", "")
        if normalize_lookup_text(descriptor) == normalized_target:
            return item

    return None


def workday_reference(value: str, match: dict[str, str] | None) -> dict[str, str]:
    """Build the CXS reference object for a degree or field-of-study value.

    Catalog membership is required before emitting ``id``: a raw 32-hex string
    without a matched catalog row falls back to ``descriptor`` (APL-24).
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("workday reference value must be non-empty")
    if match and match.get("id"):
        return {"id": match["id"]}
    return {"descriptor": stripped}


def _parse_lookup_rows(rows: list[Any]) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    for row in rows:
        item = _lookup_item(row)
        if item is not None:
            parsed.append(item)
    return parsed


def _lookup_item(row: Any) -> dict[str, str] | None:
    if not isinstance(row, dict):
        return None
    item_id = _first_text(row.get("id"), row.get("wid"))
    descriptor = _first_text(row.get("descriptor"), row.get("label"), row.get("name"))
    if not item_id and not descriptor:
        return None
    parsed: dict[str, str] = {}
    if item_id:
        parsed["id"] = item_id
    if descriptor:
        parsed["descriptor"] = descriptor
    return parsed or None


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
