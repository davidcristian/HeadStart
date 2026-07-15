"""US/EU salary amount token parsing for compensation extraction."""

from __future__ import annotations

import re

# Amount tokens accept both US (1,234.56) and EU (1.234,56 / 55.000) separators;
# `normalize_amount_digits` decides which chars are grouping vs decimal.
AMOUNT_RE = re.compile(
    r"(?P<symbol>[$€£])?\s*(?P<amount>\d[\d.,]*)\s*(?P<suffix>[kKmM])?",
    re.IGNORECASE,
)
RANGE_RE = re.compile(
    r"(?P<left>[$€£]?\s*\d[\d.,]*\s*[kKmM]?)"
    r"\s*(?:-|–|—|to)\s*"
    r"(?P<right>[$€£]?\s*\d[\d.,]*\s*[kKmM]?)",
    re.IGNORECASE,
)


def parse_amount(fragment: str) -> int | None:
    """Parse a salary fragment into an integer amount (before annualization)."""
    match = AMOUNT_RE.search(fragment)
    if not match:
        return None
    digits = normalize_amount_digits(match.group("amount"))
    if digits is None:
        return None
    try:
        value = float(digits)
    except ValueError:
        return None
    suffix = (match.group("suffix") or "").lower()
    if suffix in {"k", "m"}:
        multiplier = 1_000 if suffix == "k" else 1_000_000
        value *= multiplier
    return int(round(value))


def normalize_amount_digits(amount: str) -> str | None:
    """Map a US/EU grouped amount token to a float()-parseable digit string."""
    cleaned = amount.strip().rstrip(".,")
    if not cleaned or not cleaned[0].isdigit() or not re.fullmatch(r"\d[\d.,]*", cleaned):
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned
    if has_dot and has_comma:
        # Last separator is decimal; the other is thousands grouping.
        if cleaned.rfind(",") > cleaned.rfind("."):
            return cleaned.replace(".", "").replace(",", ".")
        return cleaned.replace(",", "")
    if has_comma:
        left, _, right = cleaned.partition(",")
        if "," not in right and 1 <= len(right) <= 2 and right.isdigit():
            return f"{left}.{right}"
        return cleaned.replace(",", "")
    if has_dot:
        parts = cleaned.split(".")
        if len(parts) > 2:
            # Multiple dots → EU thousands (e.g. 1.234.567).
            if all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
                return "".join(parts)
            return None
        # Exactly three fractional digits → EU thousands (55.000), not US decimal.
        if len(parts[1]) == 3 and parts[1].isdigit():
            return "".join(parts)
        return cleaned
    return cleaned
