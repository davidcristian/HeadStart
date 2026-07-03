"""Tests for portal search service."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.schemas.portal import PortalSearchRequest, PortalSubscribeRequest
from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.services.portal_search import (
    PortalSearchService,
    _build_filters,
    _has_matching_search,
    _resolve_presets,
    _resolve_subscribe_presets,
)
from tests.worker.test_pipeline import _make_search


def test_portal_search_filters_postings(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    db_session.flush()

    def fake_scrape(self, **kwargs: object) -> list[JobPosting]:
        return [
            JobPosting(external_id="1", title="Backend Engineer", company="Stripe"),
            JobPosting(external_id="2", title="Sales Manager", company="Stripe"),
        ]

    with patch.object(PipelineService, "scrape", fake_scrape):
        result = PortalSearchService(db_session).search(
            user,
            PortalSearchRequest(keywords="engineer", portal_ids=["stripe"]),
        )

    assert result.portals_searched == 1
    assert len(result.items) == 1
    assert "Engineer" in result.items[0].title


def test_portal_subscribe_reuses_existing_source(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    source = search.source
    source.name = "Stripe"
    source.adapter_key = "greenhouse"
    source.base_url = "https://boards.greenhouse.io/stripe"
    source.default_config = {
        "board_token": "stripe",
        "company": "Stripe",
        "portal_id": "stripe",
    }
    db_session.flush()

    result = PortalSearchService(db_session).subscribe(
        user,
        PortalSubscribeRequest(
            portal_ids=["stripe"],
            keywords="infra",
            target_id=search.target_id,
        ),
    )

    assert result.sources_created == 0
    assert result.searches_created == 1


def test_portal_search_caps_total_items(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    db_session.flush()

    def fake_scrape(self, **kwargs: object) -> list[JobPosting]:
        # Each portal returns more than _MAX_PER_PORTAL matches so the cap logic
        # (both per-portal and global) is exercised.
        return [JobPosting(external_id=str(i), title="Engineer", company="Co") for i in range(200)]

    with patch.object(PipelineService, "scrape", fake_scrape):
        result = PortalSearchService(db_session).search(
            user,
            PortalSearchRequest(keywords="engineer", category="ai"),
        )

    assert len(result.items) == 100


def test_portal_search_collects_errors(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    db_session.flush()

    def boom(self, **kwargs: object) -> list[JobPosting]:
        raise RuntimeError("scrape failed")

    with patch.object(PipelineService, "scrape", boom):
        result = PortalSearchService(db_session).search(
            user,
            PortalSearchRequest(keywords="engineer", portal_ids=["stripe"]),
        )

    assert result.portals_failed == 1
    assert result.errors[0].error == "scrape failed"


def test_portal_search_reuses_owned_source_id(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    source = search.source
    source.name = "Stripe"
    source.adapter_key = "greenhouse"
    source.base_url = "https://boards.greenhouse.io/stripe"
    source.default_config = {"board_token": "stripe", "portal_id": "stripe"}
    db_session.flush()

    captured: dict[str, object] = {}

    def fake_scrape(self, **kwargs: object) -> list[JobPosting]:
        captured.update(kwargs)
        return [JobPosting(external_id="1", title="Engineer", company="Stripe")]

    with patch.object(PipelineService, "scrape", fake_scrape):
        PortalSearchService(db_session).search(
            user,
            PortalSearchRequest(keywords="engineer", portal_ids=["stripe"]),
        )

    assert captured["source_id"] == source.id


def test_portal_search_builds_location_and_workplace_filters(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    db_session.flush()

    captured: dict[str, object] = {}

    def fake_scrape(self, **kwargs: object) -> list[JobPosting]:
        captured.update(kwargs)
        return []

    with patch.object(PipelineService, "scrape", fake_scrape):
        PortalSearchService(db_session).search(
            user,
            PortalSearchRequest(
                keywords="engineer",
                portal_ids=["stripe"],
                location="Berlin",
                workplace="remote",
            ),
        )

    assert captured["filters"]["location"] == "Berlin"
    assert captured["filters"]["workplace"] == "remote"


def test_subscribe_creates_source_and_digest_search(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    db_session.flush()

    result = PortalSearchService(db_session).subscribe(
        user,
        PortalSubscribeRequest(
            portal_ids=["stripe"],
            keywords="infra",
            target_id=search.target_id,
            notification_mode="digest",
        ),
    )

    assert result.sources_created == 1
    assert result.searches_created == 1


def test_subscribe_skips_duplicate_search(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "pro"
    source = search.source
    source.name = "Stripe"
    source.adapter_key = "greenhouse"
    source.base_url = "https://boards.greenhouse.io/stripe"
    source.default_config = {"board_token": "stripe", "portal_id": "stripe"}
    search.filters = {"keywords_include": "infra"}
    db_session.flush()

    result = PortalSearchService(db_session).subscribe(
        user,
        PortalSubscribeRequest(
            portal_ids=["stripe"],
            keywords="infra",
            target_id=search.target_id,
        ),
    )

    assert result.searches_created == 0
    assert result.skipped_portal_ids == ["stripe"]


def test_subscribe_stops_on_plan_limit(db_session: Session) -> None:
    search = _make_search(db_session)
    user = search.user
    user.plan = "free"  # portal_search requires pro
    user.is_admin = True  # bypass require_portal_search but keep search caps low
    db_session.flush()

    # Admin bypasses portal-search gate but plan-limit checks still apply through
    # a patched require_can_add_search that raises for coverage of the handler.
    from app.core.exceptions import PlanLimitError
    from app.services.plan_limits import PlanLimitsService

    def raise_limit(self, user_id: int) -> None:
        raise PlanLimitError("nope", code="search_limit", plan="free")

    with patch.object(PlanLimitsService, "require_can_add_search", raise_limit):
        result = PortalSearchService(db_session).subscribe(
            user,
            PortalSubscribeRequest(
                portal_ids=["stripe"],
                keywords="infra",
                target_id=search.target_id,
            ),
        )

    assert result.message == "nope"
    assert result.searches_created == 0


def test_resolve_presets_unknown_portal_id_raises() -> None:
    with pytest.raises(ValidationError, match="Unknown portal id"):
        _resolve_presets("pro", category=None, portal_ids=["does-not-exist"])


def test_resolve_subscribe_presets_unknown_portal_id_raises() -> None:
    data = PortalSubscribeRequest(portal_ids=["nope"], keywords="x", target_id=1)
    with pytest.raises(ValidationError, match="Unknown portal id"):
        _resolve_subscribe_presets(data, "pro")


def test_resolve_subscribe_presets_scraper_not_allowed_raises() -> None:
    # No curated portal uses a scraper gated above free today, so inject a preset
    # whose adapter (indeed) is gated to exercise the plan-guard branch.
    from app.portals.catalog_presets import PortalPreset

    gated_preset = PortalPreset(
        id="gated",
        company_name="Gated Co",
        category="ai",
        adapter_key="indeed",
        base_url="https://example.com",
        default_config={},
    )
    data = PortalSubscribeRequest(portal_ids=["gated"], keywords="x", target_id=1)
    with (
        patch("app.services.portal_search.get_portal_preset", return_value=gated_preset),
        pytest.raises(ValidationError, match="requires a higher plan"),
    ):
        _resolve_subscribe_presets(data, "free")


def test_build_filters_minimal() -> None:
    data = PortalSearchRequest(keywords="  engineer  ")
    assert _build_filters(data) == {"keywords_include": "engineer"}


def test_has_matching_search_uses_legacy_keywords_field(db_session: Session) -> None:
    search = _make_search(db_session)
    search.filters = {"keywords": "infra"}
    db_session.flush()

    assert _has_matching_search([search], search.source_id, {"keywords_include": "infra"}) is True
    assert _has_matching_search([search], 999, {"keywords_include": "infra"}) is False
