"""Tests for portal catalog helpers."""

from app.models.source import Source
from app.portals.catalog import list_portal_presets
from app.services.portals import _config_keys_match, _normalize_url


def test_list_portal_presets_filters_category() -> None:
    ai = list_portal_presets(category="ai")
    assert ai
    assert all(p.category == "ai" for p in ai)


def test_list_portal_presets_filters_query() -> None:
    matches = list_portal_presets(query="nvidia")
    assert len(matches) == 1
    assert matches[0].company_name == "NVIDIA"


def test_config_keys_match_greenhouse() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "stripe")
    source = Source(
        user_id=1,
        name="Stripe",
        adapter_key="greenhouse",
        base_url="https://boards.greenhouse.io/stripe",
        default_config={"board_token": "stripe"},
    )
    assert _config_keys_match(preset, source) is True


def test_normalize_url_strips_trailing_slash() -> None:
    assert _normalize_url("https://example.com/") == _normalize_url("https://example.com")
