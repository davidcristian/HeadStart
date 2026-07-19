from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.security import hash_url_token
from app.models.base import utcnow
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth import AuthService


def _register(client: TestClient, email: str = "reset@example.com") -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )


def test_forgot_password_returns_same_message_for_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert resp.status_code == 200
    assert "password reset link" in resp.json()["message"].lower()


@patch("app.services.auth_password.send_password_reset_email")
@patch("app.services.auth_password.generate_password_reset_token", return_value="known-reset-token")
def test_forgot_and_reset_password_flow(
    _mock_token: object,
    _mock_email: object,
    client: TestClient,
) -> None:
    _register(client)

    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@example.com"},
    )
    assert forgot.status_code == 200

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "known-reset-token", "password": "new-password-99"},
    )
    assert reset.status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "reset@example.com", "password": "password123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "reset@example.com", "password": "new-password-99"},
        ).status_code
        == 200
    )


@patch("app.services.auth_password.send_password_reset_email")
@patch("app.services.auth_password.generate_password_reset_token", return_value="known-reset-token")
def test_reset_password_invalidates_captured_refresh_token(
    _mock_token: object,
    _mock_email: object,
    client: TestClient,
) -> None:
    """A refresh token captured before recovery must not survive the reset."""
    _register(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    captured_refresh = client.cookies.get("headstart_refresh")
    assert captured_refresh

    # Simulate a non-browser API client replaying the captured token (no cookie):
    # it works before the reset...
    client.cookies.clear()
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": captured_refresh}).status_code
        == 200
    )

    client.cookies.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "known-reset-token", "password": "new-password-99"},
    )
    assert reset.status_code == 200

    # ...and is rejected afterwards.
    client.cookies.clear()
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": captured_refresh}).status_code
        == 400
    )


@patch("app.services.auth_password.send_password_reset_email")
@patch("app.services.auth_password.generate_password_reset_token", return_value="known-reset-token")
def test_reset_password_invalidates_existing_access_token(
    _mock_token: object,
    _mock_email: object,
    client: TestClient,
) -> None:
    """An access token issued before the reset stops authenticating after it."""
    _register(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    client.cookies.clear()
    client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": "known-reset-token", "password": "new-password-99"},
        ).status_code
        == 200
    )

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_reset_password_bumps_token_version(db_session) -> None:
    user = UserRepository(db_session).add(
        User(
            email="ver@example.com",
            password_hash="hash",
            is_admin=False,
            is_active=True,
        )
    )
    PasswordResetTokenRepository(db_session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_url_token("ver-token"),
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    db_session.commit()
    assert user.token_version == 0

    AuthService(db_session).reset_password(
        ResetPasswordRequest(token="ver-token", password="new-password-99")
    )
    db_session.refresh(user)
    assert user.token_version == 1


def test_token_without_ver_claim_is_rejected(client: TestClient) -> None:
    """Legacy tokens minted before this feature carry no `ver` and must be treated
    as stale — guards against a future `payload.get("ver", user.token_version)`
    regression that would silently revive them across a reset."""
    _register(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "password123"},
    )
    user_id = jwt.decode(
        login.json()["access_token"],
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )["sub"]

    now = utcnow()

    def _legacy(token_type: str, ttl: timedelta) -> str:
        return jwt.encode(
            {"sub": str(user_id), "type": token_type, "iat": now, "exp": now + ttl},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

    legacy_access = _legacy("access", timedelta(minutes=30))
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy_access}"}
        ).status_code
        == 401
    )

    client.cookies.clear()
    legacy_refresh = _legacy("refresh", timedelta(days=7))
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": legacy_refresh}).status_code
        == 400
    )


def test_reset_password_rejects_invalid_token(client: TestClient) -> None:
    _register(client)
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "password": "new-password-99"},
    )
    assert resp.status_code == 400


def test_request_password_reset_creates_token(db_session) -> None:
    user = UserRepository(db_session).add(
        User(
            email="svc@example.com",
            password_hash="hash",
            is_admin=False,
            is_active=True,
        )
    )
    db_session.commit()

    with (
        patch("app.services.auth_password.send_password_reset_email") as mock_email,
        patch("app.services.auth_password.generate_password_reset_token", return_value="svc-token"),
    ):
        message = AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email="svc@example.com")
        )

    assert "password reset link" in message.lower()
    mock_email.assert_called_once()
    row = PasswordResetTokenRepository(db_session).get_valid_by_hash(
        hash_url_token("svc-token"),
        now=utcnow(),
    )
    assert row is not None
    assert row.user_id == user.id


def test_reset_password_rejects_expired_token(db_session) -> None:
    user = UserRepository(db_session).add(
        User(
            email="exp@example.com",
            password_hash="hash",
            is_admin=False,
            is_active=True,
        )
    )
    PasswordResetTokenRepository(db_session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_url_token("expired-token"),
            expires_at=utcnow().replace(year=2000),
        )
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="expired"):
        AuthService(db_session).reset_password(
            ResetPasswordRequest(token="expired-token", password="new-password-99")
        )


def test_forgot_password_burns_token_crypto_for_unknown_email(db_session) -> None:
    """Unknown emails still generate+hash a token so timing matches the hit path (AUT-26)."""
    with (
        patch("app.services.auth_password.send_password_reset_email") as mock_email,
        patch(
            "app.services.auth_password.generate_password_reset_token",
            return_value="discarded-token",
        ) as mock_generate,
        patch(
            "app.services.auth_password.hash_url_token",
            return_value="discarded-hash",
        ) as mock_hash,
    ):
        message = AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email="nobody@example.com")
        )

    assert "password reset link" in message.lower()
    mock_generate.assert_called_once()
    mock_hash.assert_called_once_with("discarded-token")
    mock_email.assert_not_called()
    assert (
        PasswordResetTokenRepository(db_session).get_valid_by_hash(
            "discarded-hash",
            now=utcnow(),
        )
        is None
    )


def test_forgot_password_defers_email_via_scheduler(db_session) -> None:
    """When schedule_email is set, SMTP is not invoked on the request path (AUT-26)."""
    UserRepository(db_session).add(
        User(
            email="defer@example.com",
            password_hash="hash",
            is_admin=False,
            is_active=True,
        )
    )
    db_session.commit()

    scheduled: list[tuple[object, dict[str, str]]] = []

    def _schedule(fn: object, **kwargs: str) -> None:
        scheduled.append((fn, kwargs))

    with (
        patch("app.services.auth_password.send_password_reset_email") as mock_email,
        patch(
            "app.services.auth_password.generate_password_reset_token",
            return_value="defer-token",
        ),
    ):
        AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email="defer@example.com"),
            schedule_email=_schedule,
        )

    mock_email.assert_not_called()
    assert len(scheduled) == 1
    fn, kwargs = scheduled[0]
    assert kwargs["to_email"] == "defer@example.com"
    assert "defer-token" in kwargs["reset_url"]
    fn(**kwargs)  # type: ignore[operator]
    mock_email.assert_called_once_with(
        to_email="defer@example.com",
        reset_url=kwargs["reset_url"],
        locale=None,
    )


def test_forgot_password_unknown_email_does_not_schedule(db_session) -> None:
    scheduled: list[object] = []

    def _schedule(fn: object, **kwargs: str) -> None:
        scheduled.append(fn)

    with patch("app.services.auth_password.send_password_reset_email") as mock_email:
        AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email="ghost@example.com"),
            schedule_email=_schedule,
        )

    assert scheduled == []
    mock_email.assert_not_called()
