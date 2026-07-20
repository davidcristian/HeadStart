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

    assert len(CURATED_PORTALS) == 120


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


def test_curated_portal_uber_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "uber")
    assert preset.adapter_key == "uber_careers"
    assert preset.default_config["portal_id"] == "uber"
    assert preset.base_url == "https://www.uber.com/us/en/careers/list/"


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


def test_curated_portal_hubspot_board_token() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "hubspot")
    assert preset.adapter_key == "greenhouse"
    assert preset.default_config["board_token"] == "hubspotjobs"
    assert preset.default_config["portal_id"] == "hubspot"


def test_curated_portal_zoom_workday_config() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "zoom")
    assert preset.adapter_key == "workday"
    assert preset.default_config["tenant"] == "zoom"
    assert preset.default_config["site"] == "Zoom"
    assert preset.default_config["region"] == "wd5"


def test_curated_portal_atlassian_smartrecruiters_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "atlassian")
    assert preset.adapter_key == "smartrecruiters"
    assert preset.default_config["company_id"] == "Atlassian2"
    assert preset.default_config["portal_id"] == "atlassian"
    assert preset.base_url == "https://careers.smartrecruiters.com/Atlassian2"


def test_curated_portal_shopify_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "shopify")
    assert preset.adapter_key == "shopify_careers"
    assert preset.default_config["portal_id"] == "shopify"
    assert preset.default_config["company"] == "Shopify"
    assert "board" not in preset.default_config
    assert preset.base_url == "https://www.shopify.com/careers"


def test_curated_portal_snowflake_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "snowflake")
    assert preset.adapter_key == "snowflake_careers"
    assert preset.default_config["portal_id"] == "snowflake"
    assert preset.default_config["board"] == "snowflake"
    assert preset.base_url == "https://careers.snowflake.com/us/en/search-results"


def test_curated_portal_canva_smartrecruiters_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "canva")
    assert preset.adapter_key == "smartrecruiters"
    assert preset.default_config["company_id"] == "Canva"
    assert preset.default_config["portal_id"] == "canva"


def test_curated_portal_wiz_board_token() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "wiz")
    assert preset.adapter_key == "greenhouse"
    assert preset.default_config["board_token"] == "wizinc"


def test_curated_portal_crowdstrike_workday_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "crowdstrike")
    assert preset.adapter_key == "workday"
    assert preset.default_config["tenant"] == "crowdstrike"
    assert preset.default_config["site"] == "crowdstrikecareers"
    assert preset.default_config["region"] == "wd5"


def test_curated_portal_zillow_workday_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "zillow")
    assert preset.adapter_key == "workday"
    assert preset.default_config["tenant"] == "zillow"
    assert preset.default_config["site"] == "Zillow_Group_External"
    assert preset.default_config["region"] == "wd5"


def test_curated_portal_paloaltonetworks_workday_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "paloaltonetworks")
    assert preset.adapter_key == "workday"
    assert preset.default_config["tenant"] == "paloaltonetworks"
    assert preset.default_config["site"] == "panwexternalcareers"
    assert preset.default_config["region"] == "wd5"


def test_curated_portal_sentinelone_greenhouse_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "sentinelone")
    assert preset.adapter_key == "greenhouse"
    assert preset.default_config["board_token"] == "sentinellabs"
    assert preset.default_config["portal_id"] == "sentinelone"


def test_curated_portal_rivian_icims_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "rivian")
    assert preset.adapter_key == "icims"
    assert preset.category == "unicorn"
    assert preset.base_url == "https://careers.rivian.com"
    assert preset.default_config["careers_base_url"] == "https://careers.rivian.com"
    assert preset.default_config["portal_id"] == "rivian"
    assert preset.default_config["company"] == "Rivian"


def test_curated_portal_splunk_phenom_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS
    from app.portals.catalog_helpers_phenom import phenom_preset

    preset = next(p for p in CURATED_PORTALS if p.id == "splunk")
    assert preset.adapter_key == "phenom"
    assert preset.company_name == "Splunk"
    assert preset.category == "big_tech"
    assert preset.base_url == "https://careers.cisco.com"
    assert preset.default_config["ref_num"] == "CISCISGLOBAL"
    assert preset.default_config["keywords"] == "Splunk"
    assert preset.default_config["portal_id"] == "splunk"

    bare = phenom_preset(
        portal_id="acme",
        company="Acme",
        careers_base_url="https://careers.cisco.com/",
        country="us",
        locale="en_us",
        ref_num="ACME",
        keywords="   ",
    )
    assert "keywords" not in bare.default_config
    assert bare.default_config["careers_base_url"] == "https://careers.cisco.com"


def test_curated_portal_rippling_ats_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS
    from app.portals.catalog_helpers_rippling import rippling_preset

    preset = next(p for p in CURATED_PORTALS if p.id == "rippling")
    assert preset.adapter_key == "rippling"
    assert preset.company_name == "Rippling"
    assert preset.category == "unicorn"
    assert preset.base_url == "https://ats.rippling.com/rippling"
    assert preset.default_config["board"] == "rippling"
    assert preset.default_config["portal_id"] == "rippling"

    other = rippling_preset(
        portal_id="petfolk",
        company="Petfolk",
        board="petfolk",
        category="unicorn",
    )
    assert other.default_config["board"] == "petfolk"
    assert other.base_url == "https://ats.rippling.com/petfolk"


def test_curated_portal_confluent_ashby_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "confluent")
    assert preset.adapter_key == "ashby"
    assert preset.default_config["board"] == "confluent"


def test_curated_portal_grammarly_ashby_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "grammarly")
    assert preset.adapter_key == "ashby"
    assert preset.company_name == "Grammarly"
    assert preset.category == "unicorn"
    assert preset.default_config["board"] == "Superhuman Platform Inc"
    assert preset.default_config["portal_id"] == "grammarly"
    assert preset.base_url == "https://jobs.ashbyhq.com/Superhuman%20Platform%20Inc"


def test_curated_portal_snyk_workday_preset() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "snyk")
    assert preset.adapter_key == "workday"
    assert preset.company_name == "Snyk"
    assert preset.category == "unicorn"
    assert preset.default_config["tenant"] == "snyk"
    assert preset.default_config["site"] == "External"
    assert preset.default_config["region"] == "wd103"
    assert preset.default_config["portal_id"] == "snyk"
    assert preset.base_url == "https://snyk.wd103.myworkdayjobs.com/en-US/External"


def test_curated_portal_catalog_unique_portal_ids() -> None:
    from app.portals.catalog import CURATED_PORTALS

    portal_ids = [p.default_config["portal_id"] for p in CURATED_PORTALS]
    assert len(portal_ids) == len(set(portal_ids))


def test_config_keys_match_smartrecruiters() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "bosch")
    source = Source(
        user_id=1,
        name="Bosch",
        adapter_key="smartrecruiters",
        base_url="https://careers.smartrecruiters.com/BoschGroup",
        default_config={"company_id": "BoschGroup"},
    )
    assert _config_keys_match(preset, source) is True


def test_config_keys_match_single_employer_apple() -> None:
    # apple_careers is a portal_id-identified single-employer adapter; it must be
    # in the single-employer branch alongside its siblings (was previously omitted).
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "apple")
    source = Source(
        user_id=1,
        name="Apple",
        adapter_key="apple_careers",
        base_url="https://jobs.apple.com/en-us/search",
        default_config={"portal_id": "apple"},
    )
    assert _config_keys_match(preset, source) is True


def test_config_keys_match_single_employer_portal_id_mismatch() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.id == "apple")
    source = Source(
        user_id=1,
        name="Not Apple",
        adapter_key="apple_careers",
        base_url="https://jobs.apple.com/en-us/search",
        default_config={"portal_id": "google"},
    )
    assert _config_keys_match(preset, source) is False


def test_config_keys_match_lever() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.adapter_key == "lever")
    source = Source(
        user_id=1,
        name="Lever co",
        adapter_key="lever",
        base_url="https://jobs.lever.co/other",
        default_config={"site": preset.default_config["site"]},
    )
    assert _config_keys_match(preset, source) is True


def test_config_keys_match_ashby() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.adapter_key == "ashby")
    source = Source(
        user_id=1,
        name="Ashby co",
        adapter_key="ashby",
        base_url="https://jobs.ashbyhq.com/other",
        default_config={"board": preset.default_config["board"]},
    )
    assert _config_keys_match(preset, source) is True


def test_config_keys_match_workday() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.adapter_key == "workday")
    source = Source(
        user_id=1,
        name="Workday co",
        adapter_key="workday",
        base_url="https://other.wd5.myworkdayjobs.com/x",
        default_config={
            "tenant": preset.default_config["tenant"],
            "site": preset.default_config["site"],
        },
    )
    assert _config_keys_match(preset, source) is True


def test_config_keys_match_adapter_mismatch_is_false() -> None:
    from app.portals.catalog import CURATED_PORTALS

    preset = next(p for p in CURATED_PORTALS if p.adapter_key == "greenhouse")
    source = Source(
        user_id=1,
        name="Different adapter",
        adapter_key="lever",
        base_url="https://jobs.lever.co/x",
        default_config={},
    )
    assert _config_keys_match(preset, source) is False


def test_config_keys_match_unhandled_adapter_returns_false(monkeypatch) -> None:
    from app.portals.catalog_presets import PortalPreset

    preset = PortalPreset(
        id="x",
        company_name="X",
        category="ai",
        adapter_key="generic_html",
        base_url="https://x.example.com",
        default_config={},
    )
    source = Source(
        user_id=1,
        name="X",
        adapter_key="generic_html",
        base_url="https://x.example.com/other",
        default_config={},
    )
    assert _config_keys_match(preset, source) is False


def test_list_for_user_annotates_owned_by_portal_id(db_session) -> None:
    from app.models.user import User
    from app.portals.catalog import CURATED_PORTALS
    from app.services.portals import PortalCatalogService

    preset = next(p for p in CURATED_PORTALS if p.id == "stripe")
    user = User(email="portals@example.com", password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()
    # Source that shares the preset's portal_id -> already_added via line 63.
    db_session.add(
        Source(
            user_id=user.id,
            name="Stripe",
            adapter_key=preset.adapter_key,
            base_url="https://different.example.com",
            default_config={"portal_id": preset.default_config["portal_id"]},
        )
    )
    db_session.flush()

    result = PortalCatalogService(db_session).list_for_user(user)
    stripe_item = next(item for item in result.items if item.id == "stripe")
    assert stripe_item.already_added is True


def test_list_for_user_matches_owned_by_url(db_session) -> None:
    from app.models.user import User
    from app.portals.catalog import CURATED_PORTALS
    from app.services.portals import PortalCatalogService

    preset = next(p for p in CURATED_PORTALS if p.id == "stripe")
    user = User(email="portals2@example.com", password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()
    # No portal_id and mismatched identity keys, but same base_url -> line 65 match.
    db_session.add(
        Source(
            user_id=user.id,
            name="Stripe",
            adapter_key=preset.adapter_key,
            base_url=preset.base_url + "/",
            default_config={},
        )
    )
    db_session.flush()

    result = PortalCatalogService(db_session).list_for_user(user)
    stripe_item = next(item for item in result.items if item.id == "stripe")
    assert stripe_item.already_added is True


def test_list_for_user_matches_owned_by_config_keys(db_session) -> None:
    from app.models.user import User
    from app.portals.catalog import CURATED_PORTALS
    from app.services.portals import PortalCatalogService

    preset = next(p for p in CURATED_PORTALS if p.id == "stripe")
    user = User(email="portals4@example.com", password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()
    # No portal_id, different base_url, but matching greenhouse board_token
    # -> only _config_keys_match (line 67) can flag it as already added.
    db_session.add(
        Source(
            user_id=user.id,
            name="Stripe",
            adapter_key=preset.adapter_key,
            base_url="https://careers.stripe.example/other",
            default_config={"board_token": preset.default_config["board_token"]},
        )
    )
    db_session.flush()

    result = PortalCatalogService(db_session).list_for_user(user)
    stripe_item = next(item for item in result.items if item.id == "stripe")
    assert stripe_item.already_added is True


def test_list_for_user_not_added_when_no_match(db_session) -> None:
    from app.models.user import User
    from app.services.portals import PortalCatalogService

    user = User(email="portals3@example.com", password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()

    result = PortalCatalogService(db_session).list_for_user(user, category="ai")
    assert result.items
    assert all(item.already_added is False for item in result.items)
