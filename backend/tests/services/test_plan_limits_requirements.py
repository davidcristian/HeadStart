"""Unit tests for plan limit requirement gates."""

import pytest

from app.services.plan_limits import PlanLimitsService


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
