"""Tests for post-scrape posting filters."""

from app.scrapers.types import JobPosting
from app.services.posting_filters import (
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
