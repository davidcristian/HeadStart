"""Best-effort compensation extraction from scraped postings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.scrapers.types import JobPosting

_ANNUAL_INTERVALS = {"1 YEAR", "YEAR", "ANNUAL", "YEARLY"}
_HOURLY_INTERVALS = {"1 HOUR", "HOUR", "HOURLY"}
_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
_AMOUNT_RE = re.compile(
    r"(?P<symbol>[$€£])?\s*(?P<amount>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>[kKmM])?",
    re.IGNORECASE,
)
_RANGE_RE = re.compile(
    r"(?P<left>[$€£]?\s*\d[\d,]*(?:\.\d+)?\s*[kKmM]?)"
    r"\s*(?:-|–|—|to)\s*"
    r"(?P<right>[$€£]?\s*\d[\d,]*(?:\.\d+)?\s*[kKmM]?)",
    re.IGNORECASE,
)
_CODE_RE = re.compile(r"\b(USD|EUR|GBP)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CompensationInfo:
    """Normalized compensation used for filtering and display."""

    min_annual: int | None
    max_annual: int | None
    currency: str | None
    display: str | None


def extract_compensation(posting: JobPosting) -> CompensationInfo | None:
    """Return compensation details when they can be inferred from a posting."""
    structured = _from_raw(posting.raw)
    if structured is not None:
        return structured

    for source in (posting.title, posting.location):
        parsed = _from_text(source)
        if parsed is not None:
            return parsed
    return None


def format_compensation_display(posting: JobPosting) -> str:
    """Human-readable compensation string for storage and UI."""
    info = extract_compensation(posting)
    if info is None:
        return ""
    if info.display:
        return info.display
    if info.min_annual is None and info.max_annual is None:
        return ""
    prefix = _format_currency_prefix(info.currency)
    if info.min_annual is not None and info.max_annual is not None:
        if info.min_annual == info.max_annual:
            return f"{prefix}{_format_amount(info.min_annual)}"
        min_text = _format_amount(info.min_annual)
        max_text = _format_amount(info.max_annual)
        return f"{prefix}{min_text} – {prefix}{max_text}"
    if info.min_annual is not None:
        return f"{prefix}{_format_amount(info.min_annual)}+"
    if info.max_annual is not None:
        return f"Up to {prefix}{_format_amount(info.max_annual)}"
    return ""


def meets_min_salary(posting: JobPosting, min_salary: int, currency: str = "USD") -> bool:
    """True when compensation is unknown, incomparable, or meets the minimum."""
    info = extract_compensation(posting)
    if info is None or info.min_annual is None:
        return True
    if info.currency and info.currency.upper() != currency.upper():
        return True
    return info.min_annual >= min_salary


def _from_raw(raw: Any) -> CompensationInfo | None:
    if not isinstance(raw, dict):
        return None

    compensation = raw.get("compensation")
    if isinstance(compensation, dict):
        parsed = _from_ashby_compensation(compensation)
        if parsed is not None:
            return parsed

    for key in ("compensation", "salary", "pay", "compensationSummary"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            parsed = _from_text(value)
            if parsed is not None:
                return parsed
    return None


def _from_ashby_compensation(compensation: dict[str, Any]) -> CompensationInfo | None:
    display = _first_non_empty_str(
        compensation.get("scrapeableCompensationSalarySummary"),
        compensation.get("compensationTierSummary"),
    )
    components = compensation.get("summaryComponents")
    if isinstance(components, list):
        salary_components = [
            item
            for item in components
            if isinstance(item, dict) and item.get("compensationType") == "Salary"
        ]
        if salary_components:
            mins: list[int] = []
            maxs: list[int] = []
            currency: str | None = None
            for item in salary_components:
                interval = str(item.get("interval") or item.get("Interval") or "").upper()
                min_value = _coerce_int(item.get("minValue"))
                max_value = _coerce_int(item.get("maxValue"))
                code = item.get("currencyCode")
                if isinstance(code, str) and code.strip():
                    currency = code.strip().upper()
                if min_value is None and max_value is None:
                    continue
                annual_min = _annualize(min_value, interval)
                annual_max = _annualize(max_value, interval)
                if annual_min is not None:
                    mins.append(annual_min)
                if annual_max is not None:
                    maxs.append(annual_max)
            if mins or maxs or display:
                return CompensationInfo(
                    min_annual=min(mins) if mins else None,
                    max_annual=max(maxs) if maxs else None,
                    currency=currency,
                    display=display,
                )

    if display:
        parsed = _from_text(display)
        if parsed is not None:
            return parsed
        return CompensationInfo(min_annual=None, max_annual=None, currency=None, display=display)
    return None


def _from_text(text: str) -> CompensationInfo | None:
    cleaned = text.strip()
    if not cleaned or not re.search(r"[$€£]|\d", cleaned):
        return None

    currency = _currency_from_text(cleaned)
    range_match = _RANGE_RE.search(cleaned)
    if range_match:
        left = _parse_amount(range_match.group("left"))
        right = _parse_amount(range_match.group("right"))
        if left is None and right is None:
            return None
        min_annual = min(value for value in (left, right) if value is not None)
        max_annual = max(value for value in (left, right) if value is not None)
        return CompensationInfo(
            min_annual=min_annual,
            max_annual=max_annual,
            currency=currency,
            display=cleaned,
        )

    amount = _parse_amount(cleaned)
    if amount is None:
        return None
    return CompensationInfo(
        min_annual=amount,
        max_annual=amount,
        currency=currency,
        display=cleaned,
    )


def _parse_amount(fragment: str) -> int | None:
    match = _AMOUNT_RE.search(fragment)
    if not match:
        return None
    digits = match.group("amount").replace(",", "")
    try:
        value = float(digits)
    except ValueError:
        return None
    suffix = (match.group("suffix") or "").lower()
    if suffix in {"k", "m"}:
        multiplier = 1_000 if suffix == "k" else 1_000_000
        value *= multiplier
    return int(round(value))


def _currency_from_text(text: str) -> str | None:
    code_match = _CODE_RE.search(text)
    if code_match:
        return code_match.group(1).upper()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    return None


def _annualize(value: int | None, interval: str) -> int | None:
    if value is None:
        return None
    if interval in _ANNUAL_INTERVALS or not interval:
        return value
    if interval in _HOURLY_INTERVALS:
        return value * 2080
    return value


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str) and value.strip():
        try:
            return int(round(float(value.replace(",", ""))))
        except ValueError:
            return None
    return None


def _first_non_empty_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _format_currency_prefix(currency: str | None) -> str:
    if currency == "EUR":
        return "€"
    if currency == "GBP":
        return "£"
    return "$"


def _format_amount(value: int) -> str:
    if value >= 1_000_000:
        scaled = value / 1_000_000
        return f"{scaled:.1f}M".rstrip("0").rstrip(".")
    if value >= 1_000:
        scaled = value / 1_000
        if scaled == int(scaled):
            return f"{scaled:.0f}K"
        return f"{scaled:.1f}K".rstrip("0").rstrip(".")
    return str(value)
