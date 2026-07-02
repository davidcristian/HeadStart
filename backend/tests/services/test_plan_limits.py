"""Unit tests for plan limit helpers."""

from app.core.plans import (
    VALID_PLANS,
    notifier_allowed,
    plan_features_for,
    plan_limits_for,
    scraper_allowed,
)
from app.services.plan_limits import PlanLimitsService


def test_valid_plans_exclude_team() -> None:
    assert "team" not in VALID_PLANS
    assert frozenset({"free", "starter", "plus", "pro"}) == VALID_PLANS


def test_free_plan_limits_match_pricing() -> None:
    limits = plan_limits_for("free")
    assert limits.max_searches == 3
    assert limits.max_sources == 3
    assert limits.max_targets == 1


def test_starter_and_plus_limits_match_matrix() -> None:
    starter = plan_limits_for("starter")
    assert starter.max_searches == 5
    assert starter.max_sources == 5
    assert starter.max_targets == 2

    plus = plan_limits_for("plus")
    assert plus.max_searches == 10
    assert plus.max_sources == 10
    assert plus.max_targets == 3


def test_pro_plan_limits_match_matrix() -> None:
    limits = plan_limits_for("pro")
    assert limits.max_searches == 20
    assert limits.max_sources == 20
    assert limits.max_targets == 5


def test_free_plan_feature_gates() -> None:
    features = plan_features_for("free")
    assert features.digest_mode is False
    assert features.site_credentials is False
    assert features.ai_summaries is False
    assert features.rss_feed is False
    assert features.portal_search is False


def test_starter_plan_feature_gates() -> None:
    features = plan_features_for("starter")
    assert features.digest_mode is True
    assert features.site_credentials is False
    assert features.ai_summaries is False
    assert features.rss_feed is False
    assert features.portal_search is False


def test_plus_plan_feature_gates() -> None:
    features = plan_features_for("plus")
    assert features.digest_mode is True
    assert features.site_credentials is True
    assert features.ai_summaries is False
    assert features.rss_feed is False
    assert features.portal_search is False


def test_pro_plan_feature_gates() -> None:
    features = plan_features_for("pro")
    assert features.digest_mode is True
    assert features.site_credentials is True
    assert features.ai_summaries is True
    assert features.rss_feed is True
    assert features.portal_search is True


def test_premium_scrapers_gated_by_tier() -> None:
    assert scraper_allowed("free", "greenhouse") is True
    assert scraper_allowed("free", "indeed") is False
    assert scraper_allowed("starter", "indeed") is False
    assert scraper_allowed("plus", "indeed") is True
    assert scraper_allowed("plus", "linkedin") is True
    assert scraper_allowed("plus", "playwright") is True
    assert scraper_allowed("pro", "indeed") is True


def test_webhook_notifier_pro_only() -> None:
    assert notifier_allowed("free", "ntfy") is True
    assert notifier_allowed("free", "webhook") is False
    assert notifier_allowed("plus", "webhook") is False
    assert notifier_allowed("pro", "webhook") is True


def test_admin_snapshot_is_unlimited(db_session) -> None:
    from app.models.user import User

    user = User(
        email="admin@example.com",
        password_hash="x",
        is_admin=True,
        plan="free",
    )
    db_session.add(user)
    db_session.flush()

    snapshot = PlanLimitsService(db_session).snapshot(user)
    assert snapshot["unlimited"] is True
    assert snapshot["effective_plan"] == "pro"


def test_show_ads_only_for_free_non_admin_users(db_session) -> None:
    from app.models.user import User

    service = PlanLimitsService(db_session)
    free_user = User(email="free@example.com", password_hash="x", plan="free")
    starter_user = User(email="starter@example.com", password_hash="x", plan="starter")
    pro_user = User(email="pro@example.com", password_hash="x", plan="pro")
    admin_user = User(email="admin@example.com", password_hash="x", plan="free", is_admin=True)
    db_session.add_all([free_user, starter_user, pro_user, admin_user])
    db_session.flush()

    assert service.show_ads_for(free_user) is True
    assert service.show_ads_for(starter_user) is False
    assert service.show_ads_for(pro_user) is False
    assert service.show_ads_for(admin_user) is False
    assert service.snapshot(free_user)["show_ads"] is True
    assert service.snapshot(starter_user)["show_ads"] is False
    assert service.snapshot(pro_user)["show_ads"] is False


def test_allows_summaries_by_tier(db_session) -> None:
    from app.models.user import User

    service = PlanLimitsService(db_session)
    plus_user = User(email="plus@example.com", password_hash="x", plan="plus")
    pro_user = User(email="pro2@example.com", password_hash="x", plan="pro")
    db_session.add_all([plus_user, pro_user])
    db_session.flush()

    assert service.allows_summaries(plus_user.id) is False
    assert service.allows_summaries(pro_user.id) is True
