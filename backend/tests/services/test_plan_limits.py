"""Unit tests for plan limit helpers."""

from app.core.plans import (
    plan_features_for,
    plan_limits_for,
    scraper_allowed,
)
from app.services.plan_limits import PlanLimitsService


def test_free_plan_limits_match_pricing() -> None:
    limits = plan_limits_for("free")
    assert limits.max_searches == 3
    assert limits.max_sources == 3
    assert limits.max_targets == 1


def test_free_plan_feature_gates() -> None:
    features = plan_features_for("free")
    assert features.digest_mode is False
    assert features.rss_feed is False


def test_premium_scrapers_gated_on_free() -> None:
    assert scraper_allowed("free", "greenhouse") is True
    assert scraper_allowed("free", "indeed") is False
    assert scraper_allowed("pro", "indeed") is True


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
    assert snapshot["effective_plan"] == "team"
