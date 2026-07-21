"""Startup policy: forbid insecure defaults in non-local deployments.

A default ``jwt_secret`` lets anyone forge access/refresh tokens; a default
``credentials_secret_key`` makes every stored site credential decryptable.
Unset ``SMTP_HOST`` outside local/test would otherwise log password-reset and
email-verification URLs (token embedded) to stdout. A guessable
``NTFY_DEFAULT_TOPIC`` (e.g. ``headstart-change-me``) publishes job alerts to
a public ntfy.sh channel anyone can subscribe to. Incoherent refresh-cookie
flags (``SameSite=None`` without ``Secure``, or ``Secure`` with an ``http``
``FRONTEND_BASE_URL``) boot into silent auth breakage. The values live
here (not inline in ``config.py``) so the settings schema can stay under the
file-length cap while the policy has one obvious home.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlparse

# Placeholder secrets shipped for local dev convenience. Used as the field
# defaults in ``config.py`` and as the sentinels this module rejects in prod.
DEV_JWT_SECRET = "dev-local-jwt-secret-change-me-to-a-long-random-value"
DEV_CREDENTIALS_SECRET_KEY = "dev-local-credentials-key-change-me"
DEV_NTFY_DEFAULT_TOPIC = "headstart-change-me"

# Floor for CREDENTIALS_SECRET_KEY outside local/test. Fernet.generate_key()
# yields 44 urlsafe chars; openssl rand -hex 32 yields 64. Short custom strings
# remain brute-forceable even after scrypt stretching.
MIN_CREDENTIALS_SECRET_KEY_LEN = 32

# On ntfy.sh the topic name is the capability. Reject placeholders and short
# topics so a seeded/UI default cannot publish PII to a guessable public
# channel. 16 hex chars ≈ openssl rand -hex 8 (matches deploy docs).
MIN_NTFY_TOPIC_LEN = 16

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


def is_guessable_ntfy_topic(topic: str) -> bool:
    """True for empty, placeholder, or short topics that are unsafe on public ntfy."""
    cleaned = topic.strip()
    if not cleaned:
        return True
    if cleaned == DEV_NTFY_DEFAULT_TOPIC:
        return True
    if "change-me" in cleaned.lower():
        return True
    return len(cleaned) < MIN_NTFY_TOPIC_LEN


def assert_ntfy_topic_not_guessable(topic: str) -> None:
    """Raise ``ValueError`` when a target/seed topic is a placeholder or too short."""
    if not is_guessable_ntfy_topic(topic):
        return
    raise ValueError(
        "ntfy topic must be an unguessable secret (not empty, not a change-me "
        f"placeholder, and at least {MIN_NTFY_TOPIC_LEN} characters); "
        "on ntfy.sh the topic name is the capability. Prefer an auth token too."
    )


def generate_ntfy_topic() -> str:
    """Return a high-entropy topic suitable for public ntfy.sh."""
    return f"jobs-{secrets.token_hex(8)}"


def assert_ntfy_topic_safe_for_environment(environment: str, ntfy_default_topic: str) -> None:
    """Raise ``ValueError`` if a non-local env keeps the guessable ntfy topic default."""
    if is_local_environment(environment):
        return
    if not is_guessable_ntfy_topic(ntfy_default_topic):
        return
    raise ValueError(
        f"NTFY_DEFAULT_TOPIC must be set to an unguessable value when "
        f"ENVIRONMENT='{environment}'; ntfy.sh topics are public by name."
    )


def assert_auth_cookie_coherent_for_environment(
    environment: str,
    auth_cookie_secure: bool,
    auth_cookie_samesite: str,
    frontend_base_url: str,
) -> None:
    """Reject SameSite=None without Secure, or Secure cookies with an http frontend URL."""
    if is_local_environment(environment):
        return
    samesite = auth_cookie_samesite.strip().lower()
    if samesite == "none" and not auth_cookie_secure:
        raise ValueError(
            f"AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true when "
            f"ENVIRONMENT='{environment}' (browsers reject insecure SameSite=None)."
        )
    if not auth_cookie_secure:
        return
    scheme = urlparse(frontend_base_url.strip()).scheme.lower()
    if scheme == "https":
        return
    raise ValueError(
        f"AUTH_COOKIE_SECURE=true requires an https FRONTEND_BASE_URL when "
        f"ENVIRONMENT='{environment}' (got scheme={scheme!r}); "
        "set AUTH_COOKIE_SECURE=false for plain-HTTP frontends."
    )


def assert_boot_safe_for_environment(
    environment: str,
    jwt_secret: str,
    credentials_secret_key: str,
    smtp_host: str,
    ntfy_default_topic: str,
    *,
    auth_cookie_secure: bool = True,
    auth_cookie_samesite: str = "lax",
    frontend_base_url: str = "https://example.invalid",
) -> None:
    """Run every non-local startup guard (secrets, SMTP, ntfy, cookie coherence)."""
    assert_secrets_safe_for_environment(environment, jwt_secret, credentials_secret_key)
    assert_smtp_configured_for_environment(environment, smtp_host)
    assert_ntfy_topic_safe_for_environment(environment, ntfy_default_topic)
    assert_auth_cookie_coherent_for_environment(
        environment,
        auth_cookie_secure,
        auth_cookie_samesite,
        frontend_base_url,
    )
