"""Email verification API tests."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationError
from app.core.security import hash_password_reset_token
from app.models.base import utcnow
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.repositories.email_verification_tokens import EmailVerificationTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import VerifyEmailRequest
from app.services.auth import AuthService


def _register(client: TestClient, email: str = "verify@example.com") -> None:
    with (
        patch("app.services.auth.send_verification_email"),
        patch("app.services.auth.generate_password_reset_token", return_value="known-verify-token"),
    ):
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123"},
        )


def _login(client: TestClient, email: str = "verify@example.com") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_sends_verification_email_and_blocks_app_until_verified(
    client: TestClient,
) -> None:
    _register(client)
    headers = _login(client)

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email_verified_at"] is None

    blocked = client.get("/api/v1/searches", headers=headers)
    assert blocked.status_code == 403
    assert "verify" in blocked.json()["detail"].lower()

    verify = client.post(
        "/api/v1/auth/verify-email",
        json={"token": "known-verify-token"},
    )
    assert verify.status_code == 200
    assert verify.json()["email_verified_at"] is not None

    allowed = client.get("/api/v1/searches", headers=headers)
    assert allowed.status_code == 200


def test_verify_email_rejects_invalid_token(client: TestClient) -> None:
    _register(client)
    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"token": "not-a-real-token"},
    )
    assert resp.status_code == 400


def test_resend_verification_requires_unverified_user(client: TestClient) -> None:
    _register(client, email="resend@example.com")
    headers = _login(client, email="resend@example.com")

    with (
        patch("app.services.auth.send_verification_email") as mock_email,
        patch("app.services.auth.generate_password_reset_token", return_value="resend-token"),
    ):
        first = client.post("/api/v1/auth/resend-verification", headers=headers)
        assert first.status_code == 200

    mock_email.assert_called_once()

    client.post("/api/v1/auth/verify-email", json={"token": "resend-token"})

    already = client.post("/api/v1/auth/resend-verification", headers=headers)
    assert already.status_code == 400


def test_verify_email_service_marks_user_verified(db_session) -> None:
    user = UserRepository(db_session).add(
        User(
            email="svc@example.com",
            password_hash="hash",
            is_admin=False,
            is_active=True,
        )
    )
    EmailVerificationTokenRepository(db_session).add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_password_reset_token("svc-token"),
            expires_at=utcnow().replace(year=2100),
        )
    )
    db_session.commit()

    verified = AuthService(db_session).verify_email(VerifyEmailRequest(token="svc-token"))
    assert verified.email_verified_at is not None
    assert (
        EmailVerificationTokenRepository(db_session).get_valid_by_hash(
            hash_password_reset_token("svc-token"),
            now=utcnow(),
        )
        is None
    )


def test_verify_email_rejects_expired_token(db_session) -> None:
    user = UserRepository(db_session).add(
        User(
            email="exp@example.com",
            password_hash="hash",
            is_admin=False,
            is_active=True,
        )
    )
    EmailVerificationTokenRepository(db_session).add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_password_reset_token("expired-token"),
            expires_at=utcnow().replace(year=2000),
        )
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="expired"):
        AuthService(db_session).verify_email(VerifyEmailRequest(token="expired-token"))
