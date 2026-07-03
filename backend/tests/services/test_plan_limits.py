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


def test_require_user_missing_raises(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    with pytest.raises(PlanLimitError) as exc:
        service.require_can_add_search(999999)
    assert exc.value.code == "user_not_found"


def _make_user(db_session, plan: str = "free", is_admin: bool = False):
    from app.models.user import User

    user = User(
        email=f"{plan}-{is_admin}@example.com",
        password_hash="x",
        plan=plan,
        is_admin=is_admin,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_admin_bypasses_all_requirements(db_session) -> None:
    service = PlanLimitsService(db_session)
    admin = _make_user(db_session, plan="free", is_admin=True)

    # None of these raise for an admin.
    service.require_can_add_source(admin.id, "indeed")
    service.require_can_update_source_adapter(admin.id, "indeed")
    service.require_can_add_search(admin.id)
    service.require_digest_mode(admin.id)
    service.require_can_add_target(admin.id, "webhook")
    service.require_can_update_target_type(admin.id, "webhook")
    service.require_site_credentials(admin.id)
    service.require_rss_feed(admin)
    service.require_portal_search(admin)


def test_require_can_add_source_ok_and_premium_scraper_blocked(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    pro = _make_user(db_session, plan="pro")
    free = _make_user(db_session, plan="free")

    service.require_can_add_source(pro.id, "greenhouse")
    with pytest.raises(PlanLimitError) as exc:
        service.require_can_add_source(free.id, "indeed")
    assert exc.value.code == "premium_scraper"


def test_require_can_update_source_adapter_non_admin(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    free = _make_user(db_session, plan="free")
    service.require_can_update_source_adapter(free.id, "greenhouse")
    with pytest.raises(PlanLimitError):
        service.require_can_update_source_adapter(free.id, "indeed")


def test_require_digest_mode_blocks_free(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    free = _make_user(db_session, plan="free")
    starter = _make_user(db_session, plan="starter")
    service.require_digest_mode(starter.id)
    with pytest.raises(PlanLimitError) as exc:
        service.require_digest_mode(free.id)
    assert exc.value.code == "digest_mode"


def test_require_can_add_target_ok_and_premium_notifier_blocked(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    pro = _make_user(db_session, plan="pro")
    free = _make_user(db_session, plan="free")
    service.require_can_add_target(pro.id, "webhook")
    with pytest.raises(PlanLimitError) as exc:
        service.require_can_add_target(free.id, "webhook")
    assert exc.value.code == "premium_notifier"


def test_require_can_update_target_type_non_admin(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    free = _make_user(db_session, plan="free")
    service.require_can_update_target_type(free.id, "ntfy")
    with pytest.raises(PlanLimitError):
        service.require_can_update_target_type(free.id, "webhook")


def test_require_site_credentials_gate(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    plus = _make_user(db_session, plan="plus")
    free = _make_user(db_session, plan="free")
    service.require_site_credentials(plus.id)
    with pytest.raises(PlanLimitError) as exc:
        service.require_site_credentials(free.id)
    assert exc.value.code == "site_credentials"


def test_require_rss_and_portal_search_gates(db_session) -> None:
    from app.core.exceptions import PlanLimitError

    service = PlanLimitsService(db_session)
    pro = _make_user(db_session, plan="pro")
    free = _make_user(db_session, plan="free")
    service.require_rss_feed(pro)
    service.require_portal_search(pro)
    with pytest.raises(PlanLimitError) as rss_exc:
        service.require_rss_feed(free)
    assert rss_exc.value.code == "rss_feed"
    with pytest.raises(PlanLimitError) as portal_exc:
        service.require_portal_search(free)
    assert portal_exc.value.code == "portal_search"


def test_under_cap_blocks_when_at_limit(db_session) -> None:
    from app.core.exceptions import PlanLimitError
    from app.models.search import Search
    from app.models.source import Source

    service = PlanLimitsService(db_session)
    free = _make_user(db_session, plan="free")
    source = Source(
        user_id=free.id, name="s", adapter_key="greenhouse", base_url="", default_config={}
    )
    db_session.add(source)
    db_session.flush()
    # free allows 3 searches; create 3 to hit the cap.
    for i in range(3):
        db_session.add(
            Search(
                user_id=free.id,
                name=f"s{i}",
                source_id=source.id,
                query_url="",
                filters={},
                config={},
                interval_seconds=300,
                enabled=True,
            )
        )
    db_session.flush()
    with pytest.raises(PlanLimitError) as exc:
        service.require_can_add_search(free.id)
    assert exc.value.code == "search_limit"
