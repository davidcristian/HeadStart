"""Unit tests for plan limit helpers."""

import pytest

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
    assert limits.max_auto_applies_per_day == 3


def test_starter_and_plus_limits_match_matrix() -> None:
    starter = plan_limits_for("starter")
    assert starter.max_searches == 5
    assert starter.max_sources == 5
    assert starter.max_targets == 2
    assert starter.max_auto_applies_per_day == 5

    plus = plan_limits_for("plus")
    assert plus.max_searches == 10
    assert plus.max_sources == 10
    assert plus.max_targets == 3
    assert plus.max_auto_applies_per_day == 10


def test_pro_plan_limits_match_matrix() -> None:
    limits = plan_limits_for("pro")
    assert limits.max_searches == 20
    assert limits.max_sources == 20
    assert limits.max_targets == 5
    assert limits.max_auto_applies_per_day == 20


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


def test_unknown_scraper_fails_closed() -> None:
    """Unclassified adapter keys must not unlock on any plan."""
    for plan in ("free", "starter", "plus", "pro"):
        assert scraper_allowed(plan, "not_a_real_scraper") is False


def test_every_registered_scraper_is_plan_classified() -> None:
    """Registry keys must be listed in FREE_SCRAPERS or PREMIUM_SCRAPERS."""
    from app.core.plans import FREE_SCRAPERS, PREMIUM_SCRAPERS
    from app.scrapers import available_scrapers

    classified = FREE_SCRAPERS | PREMIUM_SCRAPERS
    missing = sorted(set(available_scrapers()) - classified)
    assert missing == [], f"scrapers missing plan classification: {missing}"
    overlap = sorted(FREE_SCRAPERS & PREMIUM_SCRAPERS)
    assert overlap == [], f"scrapers in both free and premium sets: {overlap}"


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
    assert snapshot["plan"] == "free"
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


def test_resolve_plan_falls_back_for_unknown_plan(db_session) -> None:
    from app.core.plans import DEFAULT_PLAN
    from app.models.user import User

    service = PlanLimitsService(db_session)
    user = User(email="weird@example.com", password_hash="x", plan="legacy")
    db_session.add(user)
    db_session.flush()

    assert service.resolve_plan(user) == DEFAULT_PLAN


def test_features_for_returns_effective_plan_features(db_session) -> None:
    from app.models.user import User

    service = PlanLimitsService(db_session)
    pro = User(email="prof@example.com", password_hash="x", plan="pro")
    db_session.add(pro)
    db_session.flush()

    assert service.features_for(pro).ai_summaries is True


def test_allows_summaries_false_for_unknown_user(db_session) -> None:
    assert PlanLimitsService(db_session).allows_summaries(123456) is False


def test_allows_summaries_true_for_admin(db_session) -> None:
    from app.models.user import User

    admin = User(email="admin-sum@example.com", password_hash="x", plan="free", is_admin=True)
    db_session.add(admin)
    db_session.flush()
    assert PlanLimitsService(db_session).allows_summaries(admin.id) is True


def test_allows_scraper_and_notifier_by_tier(db_session) -> None:
    from app.models.user import User

    service = PlanLimitsService(db_session)
    free = User(email="free-gate@example.com", password_hash="x", plan="free")
    plus = User(email="plus-gate@example.com", password_hash="x", plan="plus")
    pro = User(email="pro-gate@example.com", password_hash="x", plan="pro")
    admin = User(email="admin-gate@example.com", password_hash="x", plan="free", is_admin=True)
    db_session.add_all([free, plus, pro, admin])
    db_session.flush()

    assert service.allows_scraper(free.id, "greenhouse") is True
    assert service.allows_scraper(free.id, "indeed") is False
    assert service.allows_scraper(plus.id, "indeed") is True
    assert service.allows_scraper(admin.id, "linkedin") is True
    assert service.allows_scraper(999999, "greenhouse") is False

    assert service.allows_notifier(free.id, "ntfy") is True
    assert service.allows_notifier(free.id, "webhook") is False
    assert service.allows_notifier(pro.id, "webhook") is True
    assert service.allows_notifier(admin.id, "webhook") is True
    assert service.allows_notifier(999999, "ntfy") is False


def test_require_user_missing_raises(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    with pytest.raises(PlanLimitError) as exc:
        service.require_can_add_search(999999)
    assert exc.value.code == "user_not_found"


def test_allows_pipeline_auto_apply_unknown_user(db_session) -> None:
    assert PlanLimitsService(db_session).allows_pipeline_auto_apply(999999) is False


def test_allows_pipeline_auto_apply_admin_unlimited(db_session) -> None:
    from app.models.user import User

    admin = User(email="admin-apply@example.com", password_hash="x", plan="free", is_admin=True)
    db_session.add(admin)
    db_session.flush()
    assert PlanLimitsService(db_session).allows_pipeline_auto_apply(admin.id) is True


def test_allows_pipeline_auto_apply_zero_cap_is_unlimited(db_session, monkeypatch) -> None:
    from app.core import plans as plans_mod
    from app.models.user import User
    from app.services import plan_limits as plan_limits_mod

    user = User(email="zero-cap@example.com", password_hash="x", plan="free")
    db_session.add(user)
    db_session.flush()

    monkeypatch.setattr(
        plan_limits_mod,
        "plan_limits_for",
        lambda _plan: plans_mod.PlanLimits(
            max_searches=3,
            max_sources=3,
            max_targets=1,
            max_auto_applies_per_day=0,
        ),
    )
    assert PlanLimitsService(db_session).allows_pipeline_auto_apply(user.id) is True


def test_snapshot_includes_auto_apply_volume(db_session) -> None:
    from app.models.user import User

    user = User(email="snap-apply@example.com", password_hash="x", plan="starter")
    db_session.add(user)
    db_session.flush()

    snapshot = PlanLimitsService(db_session).snapshot(user)
    assert snapshot["limits"]["max_auto_applies_per_day"] == 5
    assert snapshot["usage"]["auto_applies_last_day"] == 0
