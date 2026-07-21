"""Admin API tests."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.models.user import User
from app.services.admin import AdminService
from tests.conftest import register_and_login


def _admin_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client, email="admin@example.com", password="password123")


def _member_headers(client: TestClient) -> dict[str, str]:
    register_and_login(client, email="admin@example.com", password="password123")
    client.post(
        "/api/v1/auth/register",
        json={"email": "member@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_non_admin_cannot_list_users(client: TestClient) -> None:
    headers = _member_headers(client)
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403


def test_admin_lists_users(client: TestClient) -> None:
    headers = _admin_headers(client)
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )

    resp = client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert emails == {"admin@example.com", "other@example.com"}


def test_admin_updates_user_flags(client: TestClient) -> None:
    headers = _admin_headers(client)
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    user_id = next(
        row["id"]
        for row in client.get("/api/v1/admin/users", headers=headers).json()
        if row["email"] == "other@example.com"
    )

    resp = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"is_admin": True, "is_active": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["is_active"] is False


def test_admin_cannot_deactivate_self(client: TestClient) -> None:
    headers = _admin_headers(client)
    admin_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert resp.status_code == 400


def test_admin_cannot_remove_own_admin(client: TestClient) -> None:
    headers = _admin_headers(client)
    admin_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=headers,
        json={"is_admin": False},
    )
    assert resp.status_code == 400


def test_admin_cannot_demote_last_admin_via_service(db_session: Session) -> None:
    from app.core.exceptions import ValidationError
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="solo@example.com", password_hash="x", is_admin=True, is_active=True)
    db_session.add(admin)
    db_session.flush()

    service = AdminService(db_session)
    try:
        service.update_user(admin.id, actor_id=999, data=AdminUserUpdate(is_admin=False))
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "At least one admin" in str(exc)


def test_admin_stats_aggregate(db_session: Session) -> None:
    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(email="member@example.com", password_hash="x", is_admin=False, is_active=True)
    db_session.add_all([admin, member])
    db_session.flush()

    source = Source(
        user_id=admin.id,
        name="ACME",
        adapter_key="greenhouse",
        base_url="https://example.test",
        default_config={},
        enabled=True,
    )
    db_session.add(source)
    db_session.flush()

    search_ok = Search(
        user_id=admin.id,
        source_id=source.id,
        name="Healthy",
        query_url="https://example.test/jobs",
        enabled=True,
        last_run_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )
    search_bad = Search(
        user_id=member.id,
        source_id=source.id,
        name="Broken",
        query_url="https://example.test/broken",
        enabled=False,
        last_error="timeout",
        last_run_at=datetime(2026, 6, 28, 11, 0, tzinfo=UTC),
    )
    db_session.add_all([search_ok, search_bad])
    db_session.flush()

    job = SeenJob(
        search_id=search_ok.id,
        external_id="job-1",
        hash="abc",
        title="Engineer",
        company="ACME",
        location="Remote",
        url="https://example.test/jobs/1",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add_all(
        [
            DeliveryLog(seen_job_id=job.id, status="sent"),
            DeliveryLog(seen_job_id=job.id, status="failed", error="boom"),
        ]
    )
    db_session.flush()

    stats = AdminService(db_session).get_stats()
    assert stats.users_total == 2
    assert stats.users_active == 2
    assert stats.searches_total == 2
    assert stats.searches_enabled == 1
    assert stats.searches_with_error == 1
    assert stats.sources_total == 1
    assert stats.seen_jobs_total == 1
    assert stats.deliveries_sent == 1
    assert stats.deliveries_failed == 1
    assert len(stats.recent_errors) == 1
    assert stats.recent_errors[0].search_name == "Broken"


def test_update_user_missing_raises_not_found(db_session: Session) -> None:
    from app.core.exceptions import NotFoundError
    from app.schemas.admin import AdminUserUpdate

    with pytest.raises(NotFoundError):
        AdminService(db_session).update_user(999, actor_id=1, data=AdminUserUpdate(plan="pro"))


def test_update_user_rejects_unknown_plan(db_session: Session) -> None:
    from app.core.exceptions import ValidationError
    from app.schemas.admin import AdminUserUpdate

    target = User(email="member@example.com", password_hash="x", is_admin=False, is_active=True)
    db_session.add(target)
    db_session.flush()

    # The router-facing schema constrains plan to a Literal, so bypass validation
    # to exercise the service's own defensive guard.
    data = AdminUserUpdate.model_construct(plan="enterprise")
    with pytest.raises(ValidationError, match="Unknown plan"):
        AdminService(db_session).update_user(target.id, actor_id=1, data=data)


def test_update_user_rejects_plan_change_with_active_stripe_subscription(
    db_session: Session,
) -> None:
    """Admin plan overrides must not fight Stripe while a sub still grants access."""
    from app.core.exceptions import ValidationError
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="subscriber@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        plan="pro",
        stripe_subscription_id="sub_live",
        subscription_status="active",
    )
    db_session.add_all([admin, member])
    db_session.flush()

    with pytest.raises(ValidationError, match="active Stripe subscription"):
        AdminService(db_session).update_user(
            member.id,
            actor_id=admin.id,
            data=AdminUserUpdate(plan="free"),
        )
    db_session.refresh(member)
    assert member.plan == "pro"


def test_update_user_allows_same_plan_with_active_stripe_subscription(
    db_session: Session,
) -> None:
    """Re-sending the current plan is a no-op and must not trip the Stripe guard."""
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="subscriber@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        plan="plus",
        stripe_subscription_id="sub_live",
        subscription_status="trialing",
    )
    db_session.add_all([admin, member])
    db_session.flush()

    updated = AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(plan="plus", is_active=True),
    )
    assert updated.plan == "plus"


def test_update_user_allows_plan_change_after_stripe_canceled(
    db_session: Session,
) -> None:
    """Canceled / non-granting statuses leave plan ownership with admin overrides."""
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="ex-sub@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        plan="free",
        subscription_status="canceled",
    )
    db_session.add_all([admin, member])
    db_session.flush()

    updated = AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(plan="starter"),
    )
    assert updated.plan == "starter"


def test_update_user_persists_flags(db_session: Session) -> None:
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="member@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        token_version=0,
    )
    db_session.add_all([admin, member])
    db_session.flush()

    updated = AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(is_active=False, is_admin=True, plan="pro"),
    )
    assert updated.is_active is False
    assert updated.is_admin is True
    assert updated.plan == "pro"
    db_session.refresh(member)
    assert member.token_version == 1


def test_deactivate_bumps_token_version(db_session: Session) -> None:
    """Admin deactivation must invalidate outstanding JWTs even after reactivation."""
    from fastapi import HTTPException

    from app.api.deps import get_current_user
    from app.core.security import create_access_token
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="member@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        token_version=3,
    )
    db_session.add_all([admin, member])
    db_session.flush()
    pre_deactivation_token = create_access_token(member.id, version=member.token_version)

    AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(is_active=False),
    )
    db_session.refresh(member)
    assert member.is_active is False
    assert member.token_version == 4

    AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(is_active=True),
    )
    db_session.refresh(member)
    assert member.is_active is True
    assert member.token_version == 4

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(
            authorization=f"Bearer {pre_deactivation_token}",
            db=db_session,
        )
    assert exc_info.value.status_code == 401


def test_deactivate_noop_when_already_inactive(db_session: Session) -> None:
    """Re-sending is_active=False must not bump token_version again."""
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="member@example.com",
        password_hash="x",
        is_admin=False,
        is_active=False,
        token_version=2,
    )
    db_session.add_all([admin, member])
    db_session.flush()

    AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(is_active=False),
    )
    db_session.refresh(member)
    assert member.token_version == 2


def test_plan_only_update_does_not_bump_token_version(db_session: Session) -> None:
    from app.schemas.admin import AdminUserUpdate

    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    member = User(
        email="member@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        token_version=1,
    )
    db_session.add_all([admin, member])
    db_session.flush()

    AdminService(db_session).update_user(
        member.id,
        actor_id=admin.id,
        data=AdminUserUpdate(plan="pro"),
    )
    db_session.refresh(member)
    assert member.token_version == 1
    assert member.plan == "pro"


def test_list_data_requests_returns_recent(db_session: Session, default_test_user: User) -> None:
    from app.models.data_request_log import DataRequestLog

    db_session.add(
        DataRequestLog(
            user_id=default_test_user.id,
            user_email="who@example.com",
            request_type="export",
        )
    )
    db_session.flush()

    rows = AdminService(db_session).list_data_requests(limit=10)
    assert len(rows) == 1
    assert rows[0].request_type == "export"


def test_admin_get_stats_endpoint(client: TestClient) -> None:
    headers = _admin_headers(client)
    resp = client.get("/api/v1/admin/stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["users_total"] >= 1
    assert "recent_errors" in body
