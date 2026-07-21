from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthService


def _register_and_verify(
    client: TestClient, email: str, password: str = "password123"
) -> dict[str, str]:
    with (
        patch("app.services.auth.send_verification_email"),
        patch("app.services.auth.generate_password_reset_token", return_value="test-verify-token"),
    ):
        client.post("/api/v1/auth/register", json={"email": email, "password": password})
    client.post("/api/v1/auth/verify-email", json={"token": "test-verify-token"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_register_first_user_is_admin(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "verification link" in body["message"]
    assert "email" not in body
    assert "is_admin" not in body

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "first@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["is_admin"] is True


def test_second_user_is_not_admin(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert "verification link" in resp.json()["message"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "second@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["is_admin"] is False


def test_register_duplicate_email_does_not_enumerate(client: TestClient) -> None:
    """Duplicate register returns the same 201 ack as a fresh signup."""
    payload = {"email": "dupe@example.com", "password": "password123"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 201
    assert second.json() == first.json()
    # Original password still works; the duplicate attempt must not overwrite it.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "dupe@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "dupe@example.com", "password": "other-password"},
    )
    assert wrong.status_code == 400


def test_login_returns_access_token_and_sets_refresh_cookie(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    body = login.json()
    # The access token is in the body; the refresh token is an httpOnly cookie
    # and must never be exposed in the response body.
    assert body["access_token"]
    assert "refresh_token" not in body
    assert client.cookies.get("headstart_refresh")

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"


def test_login_wrong_password_rejected(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "x@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 400


def test_refresh_uses_cookie_and_issues_new_access_token(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "r@example.com", "password": "password123"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "r@example.com", "password": "password123"},
    )

    # No body: the refresh token rides along in the httpOnly cookie set at login.
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_refresh_rotates_cookie_and_invalidates_prior_refresh(client: TestClient) -> None:
    """Each refresh must issue a new refresh token and revoke the previous one."""
    client.post(
        "/api/v1/auth/register",
        json={"email": "rotate-api@example.com", "password": "password123"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "rotate-api@example.com", "password": "password123"},
    )
    original_refresh = client.cookies.get("headstart_refresh")
    assert original_refresh

    first = client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    rotated_refresh = client.cookies.get("headstart_refresh")
    assert rotated_refresh
    assert rotated_refresh != original_refresh

    client.cookies.set("headstart_refresh", original_refresh)
    stale = client.post("/api/v1/auth/refresh")
    assert stale.status_code == 400


def test_refresh_without_token_rejected(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 400


def test_logout_clears_refresh_cookie(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "out@example.com", "password": "password123"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "out@example.com", "password": "password123"},
    )
    assert client.cookies.get("headstart_refresh")

    assert client.post("/api/v1/auth/logout").status_code == 200
    # The cookie is gone, so a subsequent cookie-based refresh is rejected.
    assert client.post("/api/v1/auth/refresh").status_code == 400


def test_refresh_token_rejected_as_access_token(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "t@example.com", "password": "password123"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "t@example.com", "password": "password123"},
    )

    # A refresh token must not be accepted where an access token is required.
    refresh_token = client.cookies.get("headstart_refresh")
    headers = {"Authorization": f"Bearer {refresh_token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_new_user_needs_onboarding(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "new@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["onboarding_completed_at"] is None


def test_complete_onboarding_sets_timestamp(client: TestClient) -> None:
    headers = _register_and_verify(client, "onboard@example.com")

    complete = client.post("/api/v1/auth/me/complete-onboarding", headers=headers)
    assert complete.status_code == 200
    assert complete.json()["onboarding_completed_at"] is not None

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["onboarding_completed_at"] is not None


def test_complete_onboarding_is_idempotent(client: TestClient) -> None:
    headers = _register_and_verify(client, "again@example.com")

    first = client.post("/api/v1/auth/me/complete-onboarding", headers=headers)
    second = client.post("/api/v1/auth/me/complete-onboarding", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["onboarding_completed_at"] is not None
    assert second.json()["onboarding_completed_at"] is not None


def test_patch_me_sets_and_clears_locale(client: TestClient) -> None:
    """Users can set notification/auth locale preference."""
    headers = _register_and_verify(client, "locale@example.com")

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["locale"] is None

    noop = client.patch("/api/v1/auth/me", headers=headers, json={})
    assert noop.status_code == 200
    assert noop.json()["locale"] is None

    set_de = client.patch("/api/v1/auth/me", headers=headers, json={"locale": "de"})
    assert set_de.status_code == 200
    assert set_de.json()["locale"] == "de"

    clear = client.patch("/api/v1/auth/me", headers=headers, json={"locale": None})
    assert clear.status_code == 200
    assert clear.json()["locale"] is None

    bad = client.patch("/api/v1/auth/me", headers=headers, json={"locale": "fr"})
    assert bad.status_code == 422


def test_bootstrap_admin_claim_is_exclusive(db_session: Session) -> None:
    """Only one account can claim the bootstrap admin slot."""
    repo = UserRepository(db_session)
    first = repo.add(
        User(email="first@example.com", password_hash="x", is_admin=False, is_active=True)
    )
    second = repo.add(
        User(email="second@example.com", password_hash="x", is_admin=False, is_active=True)
    )
    assert repo.claim_bootstrap_admin(first.id) is True
    assert repo.claim_bootstrap_admin(second.id) is False


def test_bootstrap_claim_survives_bootstrap_user_deletion(db_session: Session) -> None:
    """Deleting the bootstrap admin must not re-open self-service admin promotion."""
    from app.models.registration_lock import RegistrationLock
    from app.schemas.auth import DeleteAccountRequest

    service = AuthService(db_session)
    bootstrap = service.register(
        RegisterRequest(email="bootstrap@example.com", password="password123")
    )
    assert bootstrap is not None
    peer = service.register(RegisterRequest(email="peer@example.com", password="password123"))
    assert peer is not None
    peer.is_admin = True
    db_session.flush()

    service.delete_account(bootstrap.id, DeleteAccountRequest(password="password123"))

    lock = db_session.get(RegistrationLock, 1)
    assert lock is not None
    assert lock.bootstrap_user_id is None
    assert lock.bootstrap_claimed is True

    late = service.register(RegisterRequest(email="late@example.com", password="password123"))
    assert late is not None
    assert late.is_admin is False
    assert UserRepository(db_session).claim_bootstrap_admin(late.id) is False


def test_register_grants_admin_only_to_bootstrap_claimant(db_session: Session) -> None:
    """Registration promotes at most one account to admin."""
    service = AuthService(db_session)
    first = service.register(RegisterRequest(email="first@example.com", password="password123"))
    second = service.register(RegisterRequest(email="second@example.com", password="password123"))
    assert first is not None and second is not None
    assert first.is_admin is True
    assert second.is_admin is False
