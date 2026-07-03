"""Unit tests for Shopify Careers HTML/stream parsing."""

from __future__ import annotations

import json

import pytest

from app.scrapers.adapters.shopify_careers_parse import parse_careers_html


def _make_shopify_html(stream: list) -> str:
    payload = json.dumps(stream, separators=(",", ":"))
    escaped = payload.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "<html><body><script>"
        f'window.__reactRouterContext.streamController.enqueue("{escaped}");'
        "</script></body></html>"
    )


def test_parse_skips_unlisted_jobs() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "listed-id",
                            "title": "Visible",
                            "isListed": True,
                        }
                    },
                    {
                        "jobPosting": {
                            "id": "hidden-id",
                            "title": "Hidden",
                            "isListed": False,
                        }
                    },
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert [p.external_id for p in postings] == ["listed-id"]


def test_parse_raises_when_stream_missing() -> None:
    with pytest.raises(ValueError, match="missing react router stream"):
        parse_careers_html("<html><body>no loader</body></html>", company="Shopify")


def test_parse_raises_when_stream_json_invalid() -> None:
    html = (
        "<html><body><script>"
        'window.__reactRouterContext.streamController.enqueue("not-json");'
        "</script></body></html>"
    )
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_careers_html(html, company="Shopify")


def test_parse_raises_when_stream_not_array() -> None:
    html = _make_shopify_html({"unexpected": "object"})
    with pytest.raises(ValueError, match="must be an array"):
        parse_careers_html(html, company="Shopify")


def test_parse_raises_when_careers_route_missing() -> None:
    html = _make_shopify_html(["other-route", {"jobPostingsWithJobs": []}])
    with pytest.raises(ValueError, match="missing careers loader data"):
        parse_careers_html(html, company="Shopify")


def test_parse_raises_when_job_missing_id() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {"jobPostingsWithJobs": [{"jobPosting": {"title": "No ID", "isListed": True}}]},
        ]
    )
    with pytest.raises(ValueError, match="missing id"):
        parse_careers_html(html, company="Shopify")


def test_parse_formats_remote_location() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "remote-id",
                            "title": "Remote Eng",
                            "workplaceType": "Remote",
                            "locationName": "EMEA",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert postings[0].location == "Remote - EMEA"


def test_parse_formats_location_without_workplace() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "onsite-id",
                            "title": "Onsite",
                            "locationName": "Toronto",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert postings[0].location == "Toronto"


def test_parse_uses_workplace_when_location_missing() -> None:
    html = _make_shopify_html(
        [
            "($locale)/careers",
            {
                "jobPostingsWithJobs": [
                    {
                        "jobPosting": {
                            "id": "hybrid-id",
                            "title": "Hybrid",
                            "workplaceType": "Hybrid",
                            "isListed": True,
                        }
                    }
                ]
            },
        ]
    )
    postings = parse_careers_html(html, company="Shopify")
    assert postings[0].location == "Hybrid"


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
