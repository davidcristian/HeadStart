"""Tests for portal config-key matching and per-user catalog annotation."""

from app.models.source import Source
from app.services.portals import _config_keys_match


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
