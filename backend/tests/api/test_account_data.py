"""Route tests for account data export and deletion."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application_artifact import ApplicationArtifact
from app.models.base import utcnow
from app.models.notification_target import NotificationTarget
from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.search import Search
from app.models.source import Source
from app.repositories.users import UserRepository
from app.schemas.auth import DeleteAccountRequest, RegisterRequest
from app.services.auth import AuthService
from tests.conftest import register_and_login


def _delete_account(
    client: TestClient,
    *,
    password: str = "password123",
    headers: dict[str, str] | None = None,
):
    """DELETE /auth/me with a JSON body (TestClient.delete does not accept json=)."""
    return client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": password},
        headers=headers,
    )


def test_export_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me/export").status_code == 401


def test_export_includes_owned_data(client: TestClient, auth_headers: dict[str, str]) -> None:
    source = client.post(
        "/api/v1/sources",
        json={
            "name": "ACME",
            "adapter_key": "greenhouse",
            "base_url": "https://boards.greenhouse.io/acme",
            "default_config": {},
            "enabled": True,
        },
        headers=auth_headers,
    ).json()
    target = client.post(
        "/api/v1/targets",
        json={"name": "Email", "type": "email", "config": {"to": "me@example.com"}},
        headers=auth_headers,
    ).json()
    client.post(
        "/api/v1/searches",
        json={
            "name": "Engineer",
            "source_id": source["id"],
            "target_id": target["id"],
            "query_url": "https://boards.greenhouse.io/acme",
            "interval_seconds": 300,
        },
        headers=auth_headers,
    )
    client.put(
        "/api/v1/profile",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/credentials",
        json={
            "source_id": source["id"],
            "name": "Session",
            "cookies": {"sid": "secret-cookie"},
        },
        headers=auth_headers,
    )

    resp = client.get("/api/v1/auth/me/export", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["format_version"] == 1
    assert body["account"]["email"] == "user@example.com"
    assert len(body["sources"]) == 1
    assert len(body["searches"]) == 1
    assert len(body["targets"]) == 1
    assert body["profile"]["full_name"] == "Ada Lovelace"
    assert body["credentials"][0]["cookies"] == {"sid": "secret-cookie"}
    assert "password_hash" not in body["account"]


def test_export_is_scoped_per_user(client: TestClient) -> None:
    alice = register_and_login(client, "alice@example.com")
    bob = register_and_login(client, "bob@example.com")

    client.post(
        "/api/v1/sources",
        json={
            "name": "Alice Co",
            "adapter_key": "greenhouse",
            "base_url": "https://example.test",
            "default_config": {},
        },
        headers=alice,
    )

    alice_export = client.get("/api/v1/auth/me/export", headers=alice).json()
    bob_export = client.get("/api/v1/auth/me/export", headers=bob).json()
    assert len(alice_export["sources"]) == 1
    assert bob_export["sources"] == []


def test_delete_requires_auth(client: TestClient) -> None:
    assert _delete_account(client).status_code == 401


def test_delete_wrong_password_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = _delete_account(client, password="wrong-password", headers=auth_headers)
    assert resp.status_code == 400
    assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 200


def test_delete_removes_account_and_clears_cookie(client: TestClient) -> None:
    headers = register_and_login(client, "gone@example.com")
    assert client.cookies.get("headstart_refresh")

    resp = _delete_account(client, headers=headers)
    assert resp.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 400


def test_delete_cascades_owned_rows(db_session: Session) -> None:
    service = AuthService(db_session)
    user = service.register(RegisterRequest(email="cascade@example.com", password="password123"))
    source = Source(
        user_id=user.id,
        name="ACME",
        adapter_key="greenhouse",
        base_url="https://example.test",
        default_config={},
        enabled=True,
    )
    target = NotificationTarget(
        user_id=user.id,
        name="ntfy",
        type="ntfy",
        config={"topic": "alerts"},
    )
    db_session.add_all([source, target])
    db_session.flush()
    db_session.add(
        Search(
            user_id=user.id,
            source_id=source.id,
            target_id=target.id,
            name="SWE",
            query_url="https://example.test/jobs",
            filters={},
            config={},
            interval_seconds=300,
            notification_mode="immediate",
            digest_interval_seconds=3600,
            enabled=True,
            next_run_at=utcnow(),
        )
    )
    db_session.flush()

    promo = PromoCode(code="CASCADE10", promo_type="percent_off", value_int=10)
    db_session.add(promo)
    db_session.flush()
    db_session.add(
        ApplicationArtifact(
            user_id=user.id,
            artifact_type="resume_pdf",
            content_sha256="a" * 64,
            filename="resume.pdf",
            content_type="application/pdf",
            size_bytes=4,
            data_ciphertext="encrypted",
        )
    )
    db_session.add(PromoRedemption(promo_code_id=promo.id, user_id=user.id))
    db_session.flush()

    service.delete_account(user.id, DeleteAccountRequest(password="password123"))

    assert UserRepository(db_session).get(user.id) is None
    assert db_session.scalar(select(func.count()).select_from(Source)) == 0
    assert db_session.scalar(select(func.count()).select_from(Search)) == 0
    assert db_session.scalar(select(func.count()).select_from(ApplicationArtifact)) == 0
    assert db_session.scalar(select(func.count()).select_from(PromoRedemption)) == 0


def test_last_admin_cannot_delete_while_other_users_exist(client: TestClient) -> None:
    admin_headers = register_and_login(client, "admin@example.com")
    register_and_login(client, "member@example.com")

    resp = _delete_account(client, headers=admin_headers)
    assert resp.status_code == 400
    assert "only admin" in resp.json()["detail"].lower()


def test_solo_admin_can_delete_only_account(client: TestClient) -> None:
    headers = register_and_login(client, "solo@example.com")
    resp = _delete_account(client, headers=headers)
    assert resp.status_code == 204
