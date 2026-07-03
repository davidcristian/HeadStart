"""Tests for compensation extraction and salary filtering."""

from app.scrapers.types import JobPosting
from app.services.compensation import (
    CompensationInfo,
    _annualize,
    _coerce_int,
    _currency_from_text,
    _format_amount,
    _from_text,
    _parse_amount,
    extract_compensation,
    format_compensation_display,
    meets_min_salary,
)
from app.services.posting_filters import matches_posting_filters


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


def test_extract_compensation_from_ashby_summary_components() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "scrapeableCompensationSalarySummary": "$211.4K - $290.6K",
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 211400,
                        "maxValue": 290600,
                    }
                ],
            }
        }
    )

    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 211400
    assert info.max_annual == 290600
    assert info.currency == "USD"
    assert format_compensation_display(posting) == "$211.4K - $290.6K"


def test_extract_compensation_from_text_range() -> None:
    posting = _posting(title="Engineer", location="Remote", raw={})
    posting = _posting(title="Engineer ($120k - $150k)", location="Remote")

    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 120_000
    assert info.max_annual == 150_000
    assert info.currency == "USD"


def test_meets_min_salary_allows_unknown() -> None:
    posting = _posting()
    assert meets_min_salary(posting, 100_000)


def test_meets_min_salary_compares_when_known() -> None:
    high = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 180000,
                        "maxValue": 220000,
                    }
                ]
            }
        }
    )
    low = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 90000,
                        "maxValue": 110000,
                    }
                ]
            }
        }
    )

    assert meets_min_salary(high, 150_000, "USD")
    assert not meets_min_salary(low, 150_000, "USD")


def test_meets_min_salary_skips_currency_mismatch() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "EUR",
                        "minValue": 50000,
                        "maxValue": 60000,
                    }
                ]
            }
        }
    )
    assert meets_min_salary(posting, 200_000, "USD")


def test_min_salary_filter_in_posting_filters() -> None:
    rich = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 200000,
                        "maxValue": 250000,
                    }
                ]
            }
        }
    )
    modest = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 120000,
                        "maxValue": 150000,
                    }
                ]
            }
        }
    )
    filters = {"min_salary": 180000, "salary_currency": "USD"}

    assert matches_posting_filters(rich, filters)
    assert not matches_posting_filters(modest, filters)


# --- extract_compensation fallbacks ---------------------------------------


def test_extract_returns_none_when_no_signal() -> None:
    posting = _posting(title="Software Engineer", location="Remote", raw={})
    assert extract_compensation(posting) is None


def test_extract_from_text_falls_back_to_location() -> None:
    posting = _posting(title="Engineer", location="Amsterdam · $90k", raw={})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 90_000


def test_extract_from_raw_non_dict_returns_none() -> None:
    posting = _posting(raw=None)
    posting.raw = []  # type: ignore[assignment]
    assert extract_compensation(posting) is None


def test_extract_from_raw_string_salary_field() -> None:
    posting = _posting(raw={"salary": "$120,000"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 120_000


# --- format_compensation_display ------------------------------------------


def test_format_display_empty_when_no_info() -> None:
    posting = _posting(title="Engineer", location="Remote", raw={})
    assert format_compensation_display(posting) == ""


def test_format_display_min_only() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 100000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "$100K+"


def test_format_display_max_only() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "EUR",
                        "maxValue": 80000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "Up to €80K"


def test_format_display_equal_min_max_collapses() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "GBP",
                        "minValue": 150000,
                        "maxValue": 150000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "£150K"


def test_format_display_range_from_structured_without_display() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 120000,
                        "maxValue": 180000,
                    }
                ]
            }
        }
    )
    assert format_compensation_display(posting) == "$120K – $180K"


# --- ashby structured extraction edge cases -------------------------------


def test_ashby_hourly_interval_annualizes() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "HOUR",
                        "currencyCode": "USD",
                        "minValue": 50,
                        "maxValue": 60,
                    }
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 50 * 2080
    assert info.max_annual == 60 * 2080


def test_ashby_skips_components_without_values() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD"},
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 100000,
                    },
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 100000


def test_ashby_display_only_when_no_components() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "scrapeableCompensationSalarySummary": "Competitive package",
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.display == "Competitive package"
    assert info.min_annual is None


def test_ashby_display_parseable_text_is_used() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "compensationTierSummary": "$200k - $250k",
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 200_000
    assert info.max_annual == 250_000


def test_ashby_empty_compensation_dict_returns_none() -> None:
    posting = _posting(raw={"compensation": {}})
    assert extract_compensation(posting) is None


# --- _from_text ------------------------------------------------------------


def test_from_text_single_amount_via_pay_field() -> None:
    posting = _posting(raw={"pay": "€75k"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 75_000
    assert info.max_annual == 75_000
    assert info.currency == "EUR"


def test_from_text_currency_code_word() -> None:
    posting = _posting(raw={"compensationSummary": "USD 130000"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.currency == "USD"
    assert info.min_annual == 130_000


def test_millions_suffix_and_display_format() -> None:
    posting = _posting(title="Founder ($1.5M)", location="Remote")
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 1_500_000
    assert format_compensation_display(posting) == "Founder ($1.5M)"


# --- meets_min_salary edge -------------------------------------------------


def test_meets_min_salary_exact_boundary() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": 100000,
                        "maxValue": 120000,
                    }
                ]
            }
        }
    )
    assert meets_min_salary(posting, 100_000, "USD") is True


# --- ashby structural branches --------------------------------------------


def test_ashby_salary_components_present_but_no_values_or_display() -> None:
    # salary_components exist but every value is None and there is no display,
    # so the structured branch yields nothing and _from_ashby returns None.
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {"compensationType": "Salary", "interval": "1 YEAR"},
                ]
            }
        }
    )
    assert extract_compensation(posting) is None


def test_ashby_no_salary_components_falls_through_to_display() -> None:
    # Components exist but none are Salary type -> salary_components empty,
    # so it falls to the display-only branch.
    posting = _posting(
        raw={
            "compensation": {
                "scrapeableCompensationSalarySummary": "Equity + benefits",
                "summaryComponents": [
                    {"compensationType": "Bonus", "interval": "1 YEAR", "minValue": 5000},
                ],
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.display == "Equity + benefits"


def test_ashby_currency_code_non_string_skipped() -> None:
    posting = _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": 123,
                        "minValue": 100000,
                    }
                ]
            }
        }
    )
    info = extract_compensation(posting)
    assert info is not None
    assert info.currency is None


def test_from_raw_first_text_field_unparseable_then_next() -> None:
    # "compensation" as a plain string is unparseable (no digits) -> loop
    # continues to "salary".
    posting = _posting(raw={"compensation": "see website", "salary": "$95k"})
    info = extract_compensation(posting)
    assert info is not None
    assert info.min_annual == 95_000


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


def test_from_text_single_amount() -> None:
    info = _from_text("$88,500")
    assert info is not None
    assert info.min_annual == 88_500
    assert info.max_annual == 88_500


def test_from_text_returns_none_when_amount_unparseable() -> None:
    # Contains a currency symbol (passes the guard) but no digits to parse.
    assert _from_text("$") is None


# --- _parse_amount --------------------------------------------------------


def test_parse_amount_no_match() -> None:
    assert _parse_amount("no numbers here") is None


def test_parse_amount_million_suffix() -> None:
    assert _parse_amount("2M") == 2_000_000


def test_parse_amount_invalid_float_returns_none(monkeypatch) -> None:
    # Force the float() conversion to fail to exercise the except branch.
    class _BadFloat:
        def __init__(self, *_a, **_k) -> None:
            raise ValueError("boom")

    monkeypatch.setattr("app.services.compensation.float", _BadFloat, raising=False)
    assert _parse_amount("$100") is None


# --- _currency_from_text --------------------------------------------------


def test_currency_from_text_none_when_absent() -> None:
    assert _currency_from_text("100000") is None


# --- _annualize -----------------------------------------------------------


def test_annualize_none_value() -> None:
    assert _annualize(None, "YEAR") is None


def test_annualize_unknown_interval_returns_value() -> None:
    assert _annualize(1000, "WEEK") == 1000


def test_annualize_hourly() -> None:
    assert _annualize(50, "HOUR") == 50 * 2080


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
