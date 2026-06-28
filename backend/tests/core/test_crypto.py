import pytest

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
