"""Unit tests for Shopify Careers HTML/stream parsing."""

from __future__ import annotations

import json

import pytest

from app.scrapers.adapters.shopify_careers_parse import (
    _detail_url,
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


def test_resolve_node_caps_depth_on_long_noncyclic_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deep non-cyclic ref chain degrades to None instead of RecursionError."""
    monkeypatch.setattr(
        "app.scrapers.adapters.shopify_careers_parse._MAX_RESOLVE_DEPTH",
        3,
    )
    # 0→1→2→3→4→"leaf": depth 0..3 resolve; the hop to 4 is past the cap.
    stream: list = [[1], [2], [3], [4], "leaf"]
    assert _resolve_node(0, stream) == [[[[None]]]]


def test_resolve_node_caps_depth_on_dict_reference_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dict-value reference chains honor the same max-depth bound."""
    monkeypatch.setattr(
        "app.scrapers.adapters.shopify_careers_parse._MAX_RESOLVE_DEPTH",
        2,
    )
    stream: list = [{"next": 1}, {"next": 2}, {"next": 3}, "leaf"]
    assert _resolve_node(0, stream) == {"next": {"next": {"next": None}}}


def test_resolve_node_rejects_entry_past_max_depth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers that already exceed the depth cap get None without indexing."""
    monkeypatch.setattr(
        "app.scrapers.adapters.shopify_careers_parse._MAX_RESOLVE_DEPTH",
        1,
    )
    assert _resolve_node(0, ["unused"], depth=2) is None


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
