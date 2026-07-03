"""Tests for the curated portal catalog lookup helpers."""

from __future__ import annotations

from app.portals.catalog import get_portal_preset, list_portal_presets


def test_list_portal_presets_blank_query_returns_all() -> None:
    """A whitespace-only query normalizes to empty and does not filter."""
    everything = list_portal_presets()
    assert list_portal_presets(query="   ") == everything


def test_list_portal_presets_matches_by_company_or_id() -> None:
    matches = list_portal_presets(query="apple")
    assert any(p.id == "apple" for p in matches)


def test_list_portal_presets_filters_by_category() -> None:
    ai = list_portal_presets(category="ai")
    assert ai
    assert all(p.category == "ai" for p in ai)


def test_get_portal_preset_found() -> None:
    preset = get_portal_preset("apple")
    assert preset is not None
    assert preset.id == "apple"


def test_get_portal_preset_missing_returns_none() -> None:
    assert get_portal_preset("no-such-portal") is None
