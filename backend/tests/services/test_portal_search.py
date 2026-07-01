"""Tests for portal search service."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.schemas.portal import PortalSearchRequest, PortalSubscribeRequest
from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from app.services.portal_search import PortalSearchService
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
