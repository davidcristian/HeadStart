"""Unit tests for Shopify Careers HTML/stream parsing (part 2)."""

from __future__ import annotations

import json

from app.scrapers.adapters.shopify_careers_parse import (
    _detail_url,
    parse_careers_html,
)


def _make_shopify_html(stream: list) -> str:
    payload = json.dumps(stream, separators=(",", ":"))
    escaped = payload.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "<html><body><script>"
        f'window.__reactRouterContext.streamController.enqueue("{escaped}");'
        "</script></body></html>"
    )


def test_parse_builds_detail_url_when_external_link_missing() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "abc-123",
                            "title": "Fallback URL",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert postings[0].url == "https://www.shopify.com/careers?ashby_jid=abc-123"


def test_parse_posted_at_from_date_only_field() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "dated-id",
                            "title": "Dated",
                            "publishedDate": "2026-03-15",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert postings[0].posted_at is not None
    assert postings[0].posted_at.year == 2026
    assert postings[0].posted_at.month == 3
    assert postings[0].posted_at.day == 15


def test_parse_ignores_invalid_posted_at_values() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "bad-date-id",
                            "title": "Bad Date",
                            "updatedAt": "not-a-real-date",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert postings[0].posted_at is None


def test_parse_skips_records_without_dict_job_posting() -> None:
    """A record whose `jobPosting` is not a dict is skipped, not crashed on."""
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {"jobPosting": "not-a-dict"},
                    {
                        "jobPosting": {
                            "id": "real-id",
                            "title": "Real",
                            "isListed": True,
                        }
                    },
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert [p.external_id for p in postings] == ["real-id"]


def test_extract_skips_careers_route_with_non_dict_loader() -> None:
    """A careers route whose loader node is not a dict is ignored and the search continues."""
    html = _make_shopify_html(
        [
            "($locale)/careers",
            ["not", "a", "dict"],
            "($locale)/careers",
            {"jobPostingsWithJobs": [{"jobPosting": {"id": "x", "isListed": True}}]},
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert [p.external_id for p in postings] == ["x"]


def test_extract_skips_careers_route_with_non_list_jobs() -> None:
    """A careers loader whose jobPostingsWithJobs isn't a list is ignored; search continues."""
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {"jobPostingsWithJobs": "not-a-list"},
            "($locale)/careers",
            {"jobPostingsWithJobs": [{"jobPosting": {"id": "y", "isListed": True}}]},
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert [p.external_id for p in postings] == ["y"]


def test_detail_url_falls_back_to_bare_careers_without_id() -> None:
    """Without an id, the detail URL degrades to the bare careers landing page."""
    assert _detail_url({}) == "https://www.shopify.com/careers"


def test_parse_posted_at_from_datetime_without_timezone() -> None:
    """A full datetime lacking a timezone is treated as UTC."""
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "naive-dt",
                            "title": "Naive",
                            "updatedAt": "2026-05-01T09:30:00",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    posted = postings[0].posted_at
    assert posted is not None
    assert posted.hour == 9
    assert posted.tzinfo is not None
    assert posted.utcoffset().total_seconds() == 0
