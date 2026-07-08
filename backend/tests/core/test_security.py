"""Unit tests for password hashing and JWT issuing/verification."""

from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_feed_token,
    create_refresh_token,
    decode_feed_token,
    decode_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    pseudonymize_email_for_audit,
    verify_password,
)
from app.models.base import utcnow


def test_hash_and_verify_password_roundtrip() -> None:
    hashed = hash_password("s3cret-pw")
    assert hashed != "s3cret-pw"
    assert verify_password("s3cret-pw", hashed) is True
    assert verify_password("wrong-pw", hashed) is False


def test_verify_password_ignores_bytes_past_72() -> None:
    # bcrypt only hashes the first 72 bytes; passwords sharing that prefix collide.
    base = "a" * 72
    hashed = hash_password(base)
    assert verify_password(base + "different-tail", hashed) is True
    assert verify_password("a" * 71 + "b" + "tail", hashed) is False


def test_verify_password_on_malformed_hash_returns_false() -> None:
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_password_reset_token_hash_is_deterministic_sha256() -> None:
    token = generate_password_reset_token()
    assert token and token == token.strip()
    digest = hash_password_reset_token(token)
    assert digest == hash_password_reset_token(token)
    assert len(digest) == 64  # sha256 hex
    assert generate_password_reset_token() != generate_password_reset_token()


def test_pseudonymize_email_for_audit_is_stable_and_opaque() -> None:
    first = pseudonymize_email_for_audit("User@Example.com")
    second = pseudonymize_email_for_audit(" user@example.com ")
    assert first == second
    assert first.startswith("erased:")
    assert "example.com" not in first
    assert first != pseudonymize_email_for_audit("other@example.com")


def test_access_token_roundtrip_carries_type_and_version() -> None:
    token = create_access_token(42, version=7)
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["ver"] == 7


def test_decode_token_enforces_type() -> None:
    refresh = create_refresh_token(1, version=0)
    with pytest.raises(TokenError, match="Expected a access token"):
        decode_token(refresh, expected_type="access")


def test_decode_token_rejects_garbage() -> None:
    with pytest.raises(TokenError):
        decode_token("not.a.jwt", expected_type="access")


def test_decode_token_rejects_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "access_token_expire_minutes", -1)
    expired = create_access_token(1, version=0)
    with pytest.raises(TokenError):
        decode_token(expired, expected_type="access")


def test_decode_token_rejects_wrong_signature() -> None:
    forged = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "ver": 0,
            "iat": utcnow(),
            "exp": utcnow() + timedelta(minutes=5),
        },
        settings.jwt_secret + "-tampered",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_token(forged, expected_type="access")


@pytest.mark.parametrize("missing_claim", ["exp", "iat", "sub", "ver"])
def test_decode_token_requires_lifetime_and_identity_claims(missing_claim: str) -> None:
    """Reject signed JWTs that omit exp/iat/sub/ver (RFC 8725 defense-in-depth)."""
    now = utcnow()
    payload: dict[str, object] = {
        "sub": "1",
        "type": "access",
        "ver": 0,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    del payload[missing_claim]
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(TokenError, match=missing_claim):
        decode_token(token, expected_type="access")


def test_feed_token_roundtrip() -> None:
    token = create_feed_token(9, version=3)
    payload = decode_feed_token(token)
    assert payload["sub"] == "9"
    assert payload["type"] == "feed"
    assert payload["ver"] == 3


def test_feed_token_uses_configured_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed JWTs expire after FEED_TOKEN_EXPIRE_DAYS, not a decade (AUT-22)."""
    monkeypatch.setattr(settings, "feed_token_expire_days", 90)
    token = create_feed_token(1, version=0)
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat"]},
    )
    assert payload["exp"] - payload["iat"] == int(timedelta(days=90).total_seconds())


def test_decode_feed_token_rejects_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "feed_token_expire_days", -1)
    expired = create_feed_token(1, version=0)
    with pytest.raises(TokenError):
        decode_feed_token(expired)


def test_decode_feed_token_rejects_non_feed_type() -> None:
    access = create_access_token(1, version=0)
    with pytest.raises(TokenError, match="Expected a feed token"):
        decode_feed_token(access)


@pytest.mark.parametrize("missing_claim", ["exp", "iat", "sub", "ver"])
def test_decode_feed_token_requires_lifetime_and_identity_claims(missing_claim: str) -> None:
    """Feed JWTs must carry exp/iat/sub/ver; missing claims fail closed."""
    now = utcnow()
    payload: dict[str, object] = {
        "sub": "1",
        "type": "feed",
        "ver": 0,
        "iat": now,
        "exp": now + timedelta(days=1),
    }
    del payload[missing_claim]
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(TokenError, match=missing_claim):
        decode_feed_token(token)
