"""Tests for Fernet encrypt/decrypt, legacy KDF decrypt, and key rotation."""

from __future__ import annotations

import base64
import hashlib

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core import crypto
from app.core.crypto import DecryptionError, decrypt, encrypt


def test_encrypt_decrypt_round_trip() -> None:
    plaintext = '{"cookies": {"sessionid": "abc123"}}'
    token = encrypt(plaintext)
    assert token != plaintext
    assert decrypt(token) == plaintext


def test_ciphertext_is_non_deterministic() -> None:
    # Fernet embeds a random IV, so the same input encrypts differently each time.
    assert encrypt("secret") != encrypt("secret")


def test_tampered_token_raises() -> None:
    token = encrypt("secret")
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(DecryptionError):
        decrypt(tampered)


def test_legacy_sha256_ciphertext_still_decrypts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy tokens (unsalted SHA-256 Fernet) remain readable via MultiFernet."""
    secret = "legacy-compatible-credentials-secret-key"
    monkeypatch.setattr(crypto.settings, "credentials_secret_key", secret)
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", "")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    legacy = Fernet(base64.urlsafe_b64encode(digest))
    token = legacy.encrypt(b"old-cookie-blob").decode("utf-8")
    assert decrypt(token) == "old-cookie-blob"


def test_new_ciphertext_is_not_sha256_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh encrypt uses scrypt; a SHA-256-only Fernet cannot read it."""
    secret = "scrypt-primary-credentials-secret-key"
    monkeypatch.setattr(crypto.settings, "credentials_secret_key", secret)
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", "")
    token = encrypt("fresh-secret")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    legacy_only = Fernet(base64.urlsafe_b64encode(digest))
    with pytest.raises(InvalidToken):
        legacy_only.decrypt(token.encode("utf-8"))
    assert decrypt(token) == "fresh-secret"


def test_previous_secret_decrypts_after_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CREDENTIALS_SECRET_KEY_PREVIOUS keeps ciphertext readable across rotation."""
    old_secret = "previous-credentials-secret-key-value"
    new_secret = "rotated-credentials-secret-key-value"
    monkeypatch.setattr(crypto.settings, "credentials_secret_key", old_secret)
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", "")
    token = encrypt("rotate-me")
    monkeypatch.setattr(crypto.settings, "credentials_secret_key", new_secret)
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", old_secret)
    assert decrypt(token) == "rotate-me"
    # New writes use the rotated primary key.
    assert decrypt(encrypt("post-rotation")) == "post-rotation"


def test_previous_equal_to_primary_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate previous secret must not break MultiFernet construction."""
    secret = "same-primary-and-previous-secret-key"
    monkeypatch.setattr(crypto.settings, "credentials_secret_key", secret)
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", secret)
    assert decrypt(encrypt("dedupe")) == "dedupe"


def test_whitespace_previous_secret_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        crypto.settings, "credentials_secret_key", "primary-only-credentials-secret-xx"
    )
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", "   ")
    assert decrypt(encrypt("blank-prev")) == "blank-prev"


def test_wrong_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        crypto.settings, "credentials_secret_key", "correct-long-credentials-secret"
    )
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", "")
    token = encrypt("secret")
    monkeypatch.setattr(
        crypto.settings, "credentials_secret_key", "wrong-long-credentials-secret-xx"
    )
    monkeypatch.setattr(crypto.settings, "credentials_secret_key_previous", "")
    with pytest.raises(DecryptionError):
        decrypt(token)
