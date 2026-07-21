"""Symmetric encryption for secrets at rest (per-site credentials).

Per-site credentials (cookies/headers/session blobs) are encrypted with Fernet
before they ever reach the database. The Fernet key is stretched from
``settings.credentials_secret_key`` via scrypt (not a fast unsalted hash).
``MultiFernet`` keeps the legacy SHA-256 derivation and an optional previous
secret so ciphertext survives the KDF upgrade and key rotation.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

# Fixed, versioned salt: slows offline guessing of CREDENTIALS_SECRET_KEY.
# Bumping the version would add a new primary without orphaning old ciphertext.
_SCRYPT_SALT = b"headstart.credentials.v1"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class DecryptionError(Exception):
    """Raised when ciphertext cannot be decrypted (wrong key or corruption)."""


def _fernet_key_from_scrypt(secret: str) -> bytes:
    """Stretch a secret into a urlsafe-base64 32-byte Fernet key via scrypt."""
    digest = hashlib.scrypt(
        secret.encode("utf-8"),
        salt=_SCRYPT_SALT,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return base64.urlsafe_b64encode(digest)


def _fernet_key_from_sha256(secret: str) -> bytes:
    """Legacy unsalted SHA-256 derivation; decrypt-only via MultiFernet."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernets_for_secret(secret: str) -> list[Fernet]:
    """Primary scrypt Fernet plus legacy SHA-256 Fernet for one secret string."""
    return [
        Fernet(_fernet_key_from_scrypt(secret)),
        Fernet(_fernet_key_from_sha256(secret)),
    ]


@lru_cache
def _multi_fernet(primary: str, previous: str) -> MultiFernet:
    """Encrypt with the primary scrypt key; decrypt with primary, legacy, and previous."""
    fernets = _fernets_for_secret(primary)
    previous_secret = previous.strip()
    if previous_secret and previous_secret != primary:
        fernets.extend(_fernets_for_secret(previous_secret))
    return MultiFernet(fernets)


def _fernet() -> MultiFernet:
    return _multi_fernet(
        settings.credentials_secret_key,
        settings.credentials_secret_key_previous,
    )


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning urlsafe token text for storage."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt` (or a legacy/previous key)."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # wrong key or tampered/corrupted ciphertext
        raise DecryptionError("Unable to decrypt stored credential.") from exc
