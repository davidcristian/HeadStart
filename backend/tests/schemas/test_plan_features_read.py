"""PlanFeaturesRead must keep snapshot feature flags."""

from app.schemas.plan import AccountPlanRead, PlanFeaturesRead


def test_plan_features_read_keeps_portal_search() -> None:
    """Serialize portal_search so /meta can gate Pro portal search in the UI."""
    features = PlanFeaturesRead.model_validate(
        {
            "digest_mode": True,
            "ai_summaries": True,
            "site_credentials": True,
            "rss_feed": True,
            "portal_search": True,
        }
    )
    assert features.portal_search is True
    assert features.model_dump()["portal_search"] is True


def test_account_plan_read_keeps_portal_search_from_snapshot() -> None:
    """AccountPlanRead.model_validate must not drop snapshot portal_search."""
    snapshot = {
        "plan": "pro",
        "effective_plan": "pro",
        "unlimited": False,
        "show_ads": False,
        "limits": {
            "max_searches": 20,
            "max_sources": 20,
            "max_targets": 5,
            "max_auto_applies_per_day": 20,
        },
        "usage": {
            "searches": 0,
            "sources": 0,
            "targets": 0,
            "auto_applies_last_day": 0,
        },
        "features": {
            "digest_mode": True,
            "ai_summaries": True,
            "site_credentials": True,
            "rss_feed": True,
            "portal_search": True,
        },
        "allowed_scrapers": ["greenhouse"],
        "allowed_notifiers": ["email"],
    }
    plan = AccountPlanRead.model_validate(snapshot)
    assert plan.features.portal_search is True
    assert plan.model_dump()["features"]["portal_search"] is True
