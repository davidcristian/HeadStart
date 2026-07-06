"""Startup policy: forbid insecure defaults in non-local deployments.

A default ``jwt_secret`` lets anyone forge access/refresh tokens; a default
``credentials_secret_key`` makes every stored site credential decryptable.
Unset ``SMTP_HOST`` outside local/test would otherwise log password-reset and
email-verification URLs (token embedded) to stdout. A guessable
``NTFY_DEFAULT_TOPIC`` (e.g. ``headstart-change-me``) publishes job alerts to
a public ntfy.sh channel anyone can subscribe to. The values live here (not
inline in ``config.py``) so the settings schema can stay under the file-length
cap while the policy has one obvious home.
"""

from __future__ import annotations

# Placeholder secrets shipped for local dev convenience. Used as the field
# defaults in ``config.py`` and as the sentinels this module rejects in prod.
DEV_JWT_SECRET = "dev-local-jwt-secret-change-me-to-a-long-random-value"
DEV_CREDENTIALS_SECRET_KEY = "dev-local-credentials-key-change-me"
DEV_NTFY_DEFAULT_TOPIC = "headstart-change-me"

# Floor for CREDENTIALS_SECRET_KEY outside local/test (AUT-05). Fernet.generate_key()
# yields 44 urlsafe chars; openssl rand -hex 32 yields 64. Short custom strings
# remain brute-forceable even after scrypt stretching.
MIN_CREDENTIALS_SECRET_KEY_LEN = 32

_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})


def is_local_environment(environment: str) -> bool:
    """True for local/test (case-insensitive); false for every other ENVIRONMENT."""
    return environment.strip().lower() in _LOCAL_ENVIRONMENTS


def assert_secrets_safe_for_environment(
    environment: str, jwt_secret: str, credentials_secret_key: str
) -> None:
    """Raise ``ValueError`` if a non-local env uses a placeholder or short key."""
    if is_local_environment(environment):
        return
    insecure: list[str] = []
    if jwt_secret == DEV_JWT_SECRET:
        insecure.append("JWT_SECRET")
    if credentials_secret_key == DEV_CREDENTIALS_SECRET_KEY:
        insecure.append("CREDENTIALS_SECRET_KEY")
    if insecure:
        raise ValueError(
            f"{', '.join(insecure)} must be overridden when "
            f"ENVIRONMENT='{environment}'; the built-in default is insecure."
        )
    if len(credentials_secret_key) < MIN_CREDENTIALS_SECRET_KEY_LEN:
        raise ValueError(
            f"CREDENTIALS_SECRET_KEY must be at least {MIN_CREDENTIALS_SECRET_KEY_LEN} "
            f"characters when ENVIRONMENT='{environment}'."
        )


def assert_smtp_configured_for_environment(environment: str, smtp_host: str) -> None:
    """Raise ``ValueError`` if a non-local env has no SMTP host (no log fallback)."""
    if is_local_environment(environment):
        return
    if smtp_host.strip():
        return
    raise ValueError(
        f"SMTP_HOST must be set when ENVIRONMENT='{environment}'; "
        "password-reset and verification links must not fall back to logging."
    )


def assert_ntfy_topic_safe_for_environment(environment: str, ntfy_default_topic: str) -> None:
    """Raise ``ValueError`` if a non-local env keeps the guessable ntfy topic default."""
    if is_local_environment(environment):
        return
    topic = ntfy_default_topic.strip()
    if topic and topic != DEV_NTFY_DEFAULT_TOPIC and "change-me" not in topic.lower():
        return
    raise ValueError(
        f"NTFY_DEFAULT_TOPIC must be set to an unguessable value when "
        f"ENVIRONMENT='{environment}'; ntfy.sh topics are public by name."
    )


def assert_boot_safe_for_environment(
    environment: str,
    jwt_secret: str,
    credentials_secret_key: str,
    smtp_host: str,
    ntfy_default_topic: str,
) -> None:
    """Run every non-local startup guard (secrets, SMTP, ntfy topic)."""
    assert_secrets_safe_for_environment(environment, jwt_secret, credentials_secret_key)
    assert_smtp_configured_for_environment(environment, smtp_host)
    assert_ntfy_topic_safe_for_environment(environment, ntfy_default_topic)
