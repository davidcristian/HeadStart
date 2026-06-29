from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthService


def test_register_first_user_is_admin(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "first@example.com"
    assert body["is_admin"] is True


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
    assert resp.json()["is_admin"] is False


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    payload = {"email": "dupe@example.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_returns_tokens_and_me_works(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
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


def test_refresh_issues_new_tokens(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "r@example.com", "password": "password123"},
    )
    refresh_token = client.post(
        "/api/v1/auth/login",
        json={"email": "r@example.com", "password": "password123"},
    ).json()["refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_refresh_token_rejected_as_access_token(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "t@example.com", "password": "password123"},
    )
    tokens = client.post(
        "/api/v1/auth/login",
        json={"email": "t@example.com", "password": "password123"},
    ).json()

    # A refresh token must not be accepted where an access token is required.
    headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


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


def test_register_grants_admin_only_to_bootstrap_claimant(db_session: Session) -> None:
    """Registration promotes at most one account to admin."""
    service = AuthService(db_session)
    first = service.register(RegisterRequest(email="first@example.com", password="password123"))
    second = service.register(RegisterRequest(email="second@example.com", password="password123"))
    assert first.is_admin is True
    assert second.is_admin is False
