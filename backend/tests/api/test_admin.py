"""Admin API tests."""

from datetime import UTC, datetime

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


def test_admin_get_stats_endpoint(client: TestClient) -> None:
    headers = _admin_headers(client)
    resp = client.get("/api/v1/admin/stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["users_total"] >= 1
    assert "recent_errors" in body
