"""Tests for compensation helper primitives and defensive branches."""

from app.scrapers.types import JobPosting
from app.services.compensation import (
    CompensationInfo,
    _annualize,
    _coerce_int,
    _currency_from_text,
    _format_amount,
    _from_text,
    _parse_amount,
    format_compensation_display,
)
from app.services.compensation_amounts import normalize_amount_digits as _normalize_amount_digits


def _posting(
    *,
    title: str = "Software Engineer",
    company: str = "ACME",
    location: str = "Amsterdam, Netherlands",
    raw: dict | None = None,
) -> JobPosting:
    return JobPosting(
        external_id="1",
        title=title,
        company=company,
        location=location,
        url="https://acme.test/1",
        raw=raw or {},
    )


# --- format_compensation_display defensive branches -----------------------


def test_format_display_empty_for_valueless_info(monkeypatch) -> None:
    posting = _posting()
    monkeypatch.setattr(
        "app.services.compensation.extract_compensation",
        lambda _p: CompensationInfo(min_annual=None, max_annual=None, currency="USD", display=None),
    )
    assert format_compensation_display(posting) == ""


# --- _from_text pure branches ---------------------------------------------


def test_from_text_none_for_plain_text() -> None:
    assert _from_text("competitive salary") is None


def test_from_text_range_both_unparseable_returns_none(monkeypatch) -> None:
    # The range regex guarantees digits on each side, so the "both sides fail to
    # parse" guard is only reachable by forcing _parse_amount to return None.
    monkeypatch.setattr("app.services.compensation._parse_amount", lambda _f: None)
    assert _from_text("$100k - $150k") is None


def test_from_text_eu_salary_range() -> None:
    info = _from_text("€50.000 - €70.000")
    assert info is not None
    assert info.min_annual == 50_000
    assert info.max_annual == 70_000
    assert info.currency == "EUR"


def test_from_text_returns_none_when_amount_unparseable() -> None:
    # Contains a currency symbol (passes the guard) but no digits to parse.
    assert _from_text("$") is None


# --- _parse_amount --------------------------------------------------------


def test_parse_amount_no_match() -> None:
    assert _parse_amount("no numbers here") is None


def test_parse_amount_million_suffix() -> None:
    assert _parse_amount("2M") == 2_000_000


def test_parse_amount_eu_thousands_dot() -> None:
    # German-style grouping: dot = thousands, not a US decimal.
    assert _parse_amount("€55.000") == 55_000
    assert _parse_amount("55.000 €") == 55_000


def test_parse_amount_eu_decimal_comma() -> None:
    assert _parse_amount("1.234,56") == 1235  # rounds
    assert _parse_amount("€1,5k") == 1_500


def test_parse_amount_us_formats_still_work() -> None:
    assert _parse_amount("$88,500") == 88_500
    assert _parse_amount("$1,234.56") == 1_235
    assert _parse_amount("$1.5M") == 1_500_000


def test_parse_amount_rejects_malformed_multi_dot() -> None:
    assert _parse_amount("1.23.45") is None


def test_normalize_amount_digits_edge_cases() -> None:
    assert _normalize_amount_digits("") is None
    assert _normalize_amount_digits(".5") is None
    assert _normalize_amount_digits("12a34") is None
    assert _normalize_amount_digits("1.234.567") == "1234567"
    assert _normalize_amount_digits("55,5") == "55.5"
    assert _normalize_amount_digits("100.") == "100"


def test_parse_amount_invalid_float_returns_none(monkeypatch) -> None:
    # Force the float() conversion to fail to exercise the except branch.
    class _BadFloat:
        def __init__(self, *_a, **_k) -> None:
            raise ValueError("boom")

    monkeypatch.setattr("app.services.compensation_amounts.float", _BadFloat, raising=False)
    assert _parse_amount("$100") is None


# --- _currency_from_text --------------------------------------------------


def test_currency_from_text_none_when_absent() -> None:
    assert _currency_from_text("100000") is None


# --- _annualize -----------------------------------------------------------


def test_annualize_none_value() -> None:
    assert _annualize(None, "YEAR") is None


def test_annualize_unknown_interval_returns_value() -> None:
    assert _annualize(1000, "BIWEEKLY") == 1000


def test_annualize_hourly() -> None:
    assert _annualize(50, "HOUR") == 50 * 2080


def test_annualize_monthly() -> None:
    assert _annualize(8000, "MONTH") == 96_000
    assert _annualize(8000, "1 MONTH") == 96_000
    assert _annualize(8000, "MONTHLY") == 96_000


def test_annualize_weekly() -> None:
    assert _annualize(2000, "WEEK") == 104_000
    assert _annualize(2000, "1 WEEK") == 104_000
    assert _annualize(2000, "WEEKLY") == 104_000


def test_annualize_daily() -> None:
    assert _annualize(400, "DAY") == 104_000
    assert _annualize(400, "1 DAY") == 104_000
    assert _annualize(400, "DAILY") == 104_000


# --- _coerce_int ----------------------------------------------------------


def test_coerce_int_variants() -> None:
    assert _coerce_int(None) is None
    assert _coerce_int(True) is None
    assert _coerce_int(42) == 42
    assert _coerce_int(3.7) == 4
    assert _coerce_int("1,250") == 1250
    assert _coerce_int("not a number") is None
    assert _coerce_int([]) is None


# --- _format_amount -------------------------------------------------------


def test_format_amount_millions_and_small() -> None:
    assert _format_amount(2_000_000) == "2.0M"
    assert _format_amount(2_500_000) == "2.5M"
    assert _format_amount(999) == "999"
    assert _format_amount(120_000) == "120K"
    assert _format_amount(125_500) == "125.5K"
