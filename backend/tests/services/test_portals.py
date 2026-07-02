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


def test_curated_portal_catalog_size() -> None:
    from app.portals.catalog import CURATED_PORTALS

    assert len(CURATED_PORTALS) == 68


def test_curated_portal_apple_preset() -> None:
    from app.portals.catalog_presets import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "apple")
    assert preset.adapter_key == "apple_careers"
    assert preset.default_config["portal_id"] == "apple"
    assert preset.base_url == "https://jobs.apple.com/en-us/search"


def test_curated_portal_meta_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "meta")
    assert preset.adapter_key == "meta_careers"
    assert preset.default_config["portal_id"] == "meta"
    assert preset.base_url == "https://www.metacareers.com/jobsearch/"


def test_curated_portal_amazon_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "amazon")
    assert preset.adapter_key == "amazon_jobs"
    assert preset.default_config["portal_id"] == "amazon"
    assert preset.base_url == "https://www.amazon.jobs/en/search"


def test_curated_portal_doordash_board_token() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "doordash")
    assert preset.adapter_key == "greenhouse"
    assert preset.default_config["board_token"] == "doordashusa"


def test_curated_portal_intel_workday_config() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "intel")
    assert preset.adapter_key == "workday"
    assert preset.default_config["tenant"] == "intel"
    assert preset.default_config["site"] == "External"
    assert preset.default_config["region"] == "wd1"


def test_curated_portal_microsoft_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "microsoft")
    assert preset.adapter_key == "microsoft_careers"
    assert preset.default_config["domain"] == "microsoft.com"
    assert preset.base_url == "https://apply.careers.microsoft.com/careers"


def test_curated_portal_lucid_board_token() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "lucid")
    assert preset.default_config["board_token"] == "lucidmotors"


def test_curated_portal_cisco_workday_config() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "cisco")
    assert preset.adapter_key == "workday"
    assert preset.default_config["tenant"] == "cisco"
    assert preset.default_config["site"] == "Cisco_Careers"


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
