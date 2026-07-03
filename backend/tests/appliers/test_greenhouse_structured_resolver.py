"""Tests for the Greenhouse education lookup resolver."""

import httpx

from app.appliers.adapters.greenhouse_structured import (
    GreenhouseEducationResolver,
    _config_default_id,
    _parse_greenhouse_items,
    build_education_lookup_resolver,
)
from app.schemas.profile import EducationEntry
from tests.conftest import make_http_client


def test_build_education_lookup_resolver_none_without_token() -> None:
    assert build_education_lookup_resolver(None, board_token=None, config={}) is None
    assert build_education_lookup_resolver(None, board_token="acme", config={}) is not None


def test_resolve_entry_returns_none_when_ids_or_year_missing() -> None:
    resolver = GreenhouseEducationResolver(None, "acme", {})
    # No numeric ids resolvable and lookups disabled (http None) → None.
    assert (
        resolver.resolve_entry(
            EducationEntry(school="Example", degree="BSc", field_of_study="CS", start_year=2016)
        )
        is None
    )


def test_resolve_id_uses_defaults_and_blank_and_digit() -> None:
    resolver = GreenhouseEducationResolver(
        None,
        "acme",
        {"default_degree_id": "111", "default_discipline_id": "222"},
    )
    entry = EducationEntry(
        school="5417077", degree="", field_of_study="", start_year=2016, end_year=2020
    )
    result = resolver.resolve_entry(entry)
    assert result is not None
    assert result["school_name_id"] == "5417077"
    assert result["degree_id"] == "111"
    assert result["discipline_id"] == "222"


def test_resolve_id_returns_none_when_lookup_disabled() -> None:
    resolver = GreenhouseEducationResolver(None, "acme", {"skip_education_lookup": True})
    assert resolver._resolve_id("school", "Example University") is None


def test_resolve_id_blank_value_returns_none() -> None:
    resolver = GreenhouseEducationResolver(None, "acme", {})
    assert resolver._resolve_id("school", "  ") is None


def test_fetch_candidates_caches_and_handles_http_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    resolver = GreenhouseEducationResolver(make_http_client(handler), "acme", {})
    first = resolver._fetch_candidates("school", "Example")
    second = resolver._fetch_candidates("school", "Example")
    assert first == []
    assert second == []
    assert calls["n"] == 1  # second call served from cache


def test_resolve_id_no_match_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    resolver = GreenhouseEducationResolver(make_http_client(handler), "acme", {})
    assert resolver._resolve_id("school", "Nonexistent School") is None


def test_parse_greenhouse_items_variants() -> None:
    assert _parse_greenhouse_items("nope") == []
    assert _parse_greenhouse_items({"items": "nope"}) == []
    assert _parse_greenhouse_items({"items": ["bad", {"id": 1, "text": "  "}, {"text": "x"}]}) == []
    assert _parse_greenhouse_items({"items": [{"id": 5, "text": "MIT"}]}) == [
        {"id": "5", "descriptor": "MIT"}
    ]


def test_config_default_id_variants() -> None:
    assert _config_default_id({"k": "1"}, "k") == "1"
    assert _config_default_id({}, "k") is None
