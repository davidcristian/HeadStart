"""Symmetric encryption for secrets at rest (per-site credentials).

Per-site credentials (cookies/headers/session blobs) are encrypted with Fernet
before they ever reach the database. The Fernet key is derived from
`settings.credentials_secret_key` so that any human-friendly string works as the
configured secret while still yielding a valid 32-byte urlsafe key.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class DecryptionError(Exception):
    """Raised when ciphertext cannot be decrypted (wrong key or corruption)."""


def _derive_key(secret: str) -> bytes:
    """Derive a urlsafe-base64 32-byte Fernet key from an arbitrary secret."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _fernet() -> Fernet:
    return Fernet(_derive_key(settings.credentials_secret_key))


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning urlsafe token text for storage."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt`."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # wrong key or tampered/corrupted ciphertext
        raise DecryptionError("Unable to decrypt stored credential.") from exc
