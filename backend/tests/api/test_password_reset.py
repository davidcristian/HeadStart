from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationError
from app.core.security import hash_password_reset_token
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


@patch("app.services.auth.send_password_reset_email")
@patch("app.services.auth.generate_password_reset_token", return_value="known-reset-token")
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
        patch("app.services.auth.send_password_reset_email") as mock_email,
        patch("app.services.auth.generate_password_reset_token", return_value="svc-token"),
    ):
        message = AuthService(db_session).request_password_reset(
            ForgotPasswordRequest(email="svc@example.com")
        )

    assert "password reset link" in message.lower()
    mock_email.assert_called_once()
    row = PasswordResetTokenRepository(db_session).get_valid_by_hash(
        hash_password_reset_token("svc-token"),
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
            token_hash=hash_password_reset_token("expired-token"),
            expires_at=utcnow().replace(year=2000),
        )
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="expired"):
        AuthService(db_session).reset_password(
            ResetPasswordRequest(token="expired-token", password="new-password-99")
        )
