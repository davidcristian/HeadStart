"""Unit tests for Shopify Careers HTML/stream parsing."""

from __future__ import annotations

import json

import pytest

from app.scrapers.adapters.shopify_careers_parse import (
    _resolve_node,
    parse_careers_html,
)


def test_resolve_node_tolerates_non_numeric_ref_key() -> None:
    """A ref-map key that isn't `_<int>` must fall back to the literal key, not crash."""
    stream = [{"_bad": 1, "_1": 2}, "resolved", "keyname"]
    assert _resolve_node(0, stream) == {"_bad": "resolved", "resolved": "keyname"}


def test_resolve_node_negative_index_returns_none() -> None:
    """A negative reference index resolves to None instead of indexing from the end."""
    assert _resolve_node(0, [[-1], "unused"]) == [None]


def test_resolve_node_cycle_returns_none() -> None:
    """A self-referential cycle is broken by the visited-index stack."""
    assert _resolve_node(0, [[0]]) == [None]


def test_resolve_node_resolves_list_of_references() -> None:
    """Integer items inside a list are resolved; non-integers pass through."""
    assert _resolve_node(0, [[1, "literal"], "resolved"]) == ["resolved", "literal"]


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
