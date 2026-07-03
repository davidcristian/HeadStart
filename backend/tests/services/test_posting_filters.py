"""Tests for post-scrape posting filters."""

from app.scrapers.types import JobPosting
from app.services.posting_filters import (
    _min_salary,
    _normalize_workplace_text,
    _normalize_workplace_token,
    _salary_currency,
    _terms,
    _workplace_terms,
    apply_posting_filters,
    infer_workplace,
    matches_posting_filters,
)


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


def test_keywords_include_matches_title() -> None:
    posting = _posting(title="Senior Backend Engineer")
    assert matches_posting_filters(posting, {"keywords": "backend"})
    assert not matches_posting_filters(posting, {"keywords": "frontend"})


def test_keywords_include_requires_all_terms() -> None:
    posting = _posting(title="Senior Backend Engineer")
    assert matches_posting_filters(posting, {"keywords": "senior backend"})
    assert not matches_posting_filters(posting, {"keywords": "senior frontend"})


def test_keywords_exclude() -> None:
    manager = _posting(title="Engineering Manager")
    engineer = _posting(title="Backend Engineer")
    filters = {"keywords": "engineer", "keywords_exclude": "manager"}
    assert not matches_posting_filters(manager, filters)
    assert matches_posting_filters(engineer, filters)


def test_location_filter() -> None:
    posting = _posting(location="Remote - EU")
    assert matches_posting_filters(posting, {"location": "remote"})
    assert not matches_posting_filters(posting, {"location": "amsterdam"})


def test_workplace_filter_from_raw() -> None:
    remote = _posting(location="", raw={"workplaceType": "Remote"})
    onsite = _posting(location="", raw={"workplaceType": "OnSite"})
    assert matches_posting_filters(remote, {"workplace": "remote"})
    assert not matches_posting_filters(onsite, {"workplace": "remote"})


def test_workplace_filter_allows_unknown() -> None:
    posting = _posting(location="Amsterdam, Netherlands")
    assert matches_posting_filters(posting, {"workplace": "remote"})


def test_infer_workplace_from_location_text() -> None:
    assert infer_workplace(_posting(location="Remote - EU")) == "remote"
    assert infer_workplace(_posting(location="Hybrid - Amsterdam")) == "hybrid"
    assert infer_workplace(_posting(location="On-site in Amsterdam")) == "onsite"


def test_apply_posting_filters_counts_removed() -> None:
    postings = [
        _posting(title="Backend Engineer"),
        _posting(title="Sales Manager"),
    ]
    kept, removed = apply_posting_filters(postings, {"keywords": "engineer"})
    assert len(kept) == 1
    assert removed == 1
    assert kept[0].title == "Backend Engineer"


def test_apply_posting_filters_short_circuits_on_empty() -> None:
    postings = [_posting()]
    assert apply_posting_filters(postings, {}) == (postings, 0)
    assert apply_posting_filters([], {"keywords": "x"}) == ([], 0)


def test_infer_workplace_from_is_remote_flag() -> None:
    assert infer_workplace(_posting(location="", raw={"isRemote": True})) == "remote"


def test_infer_workplace_ignores_non_dict_raw() -> None:
    # pydantic coerces `raw` to a dict on construction, so bypass validation to
    # exercise the defensive `isinstance(raw, dict)` guard.
    posting = JobPosting.model_construct(
        external_id="2",
        title="Engineer",
        company="ACME",
        location="Amsterdam",
        url="https://acme.test/2",
        raw="not-a-dict",
    )
    assert infer_workplace(posting) is None


def test_infer_workplace_returns_none_when_nothing_matches() -> None:
    assert infer_workplace(_posting(title="Engineer", location="Amsterdam", raw={})) is None


def _salary_posting(min_value: int) -> JobPosting:
    return _posting(
        raw={
            "compensation": {
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 YEAR",
                        "currencyCode": "USD",
                        "minValue": min_value,
                        "maxValue": min_value + 20000,
                    }
                ]
            }
        }
    )


def test_min_salary_filter_applied() -> None:
    filters = {"min_salary": 100000}
    assert not matches_posting_filters(_salary_posting(50000), filters)
    assert matches_posting_filters(_salary_posting(200000), filters)


def test_terms_handles_list_and_non_string() -> None:
    assert _terms(["senior backend", "remote"]) == ["senior", "backend", "remote"]
    assert _terms("   ") == []
    assert _terms(123) == ["123"]


def test_workplace_terms_skips_unrecognized_tokens() -> None:
    assert _workplace_terms("remote garbage hybrid") == {"remote", "hybrid"}


def test_normalize_workplace_token_variants() -> None:
    assert _normalize_workplace_token("") is None
    assert _normalize_workplace_token("fully remote") == "remote"
    assert _normalize_workplace_token("hybrid role") == "hybrid"
    assert _normalize_workplace_token("on site only") == "onsite"
    assert _normalize_workplace_token("flexible") is None


def test_min_salary_coercions() -> None:
    assert _min_salary(None) is None
    assert _min_salary("") is None
    assert _min_salary(True) is None
    assert _min_salary(0) is None
    assert _min_salary(120000) == 120000
    assert _min_salary(99999.6) == 100000
    assert _min_salary(0.0) is None
    assert _min_salary("120,000") == 120000
    assert _min_salary("-5") is None
    assert _min_salary("not-a-number") is None
    assert _min_salary([]) is None


def test_salary_currency_defaults_and_normalizes() -> None:
    assert _salary_currency("eur") == "EUR"
    assert _salary_currency("") == "USD"
    assert _salary_currency(None) == "USD"


def test_normalize_workplace_text_empty_and_unmatched() -> None:
    assert _normalize_workplace_text("") is None
    assert _normalize_workplace_text("Amsterdam office") is None
