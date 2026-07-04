"""Startup policy: forbid insecure defaults in non-local deployments.

A default ``jwt_secret`` lets anyone forge access/refresh tokens; a default
``credentials_secret_key`` makes every stored site credential decryptable.
Unset ``SMTP_HOST`` outside local/test would otherwise log password-reset and
email-verification URLs (token embedded) to stdout. The values live here (not
inline in ``config.py``) so the settings schema can stay under the file-length
cap while the policy has one obvious home.
"""

from __future__ import annotations

# Placeholder secrets shipped for local dev convenience. Used as the field
# defaults in ``config.py`` and as the sentinels this module rejects in prod.
DEV_JWT_SECRET = "dev-local-jwt-secret-change-me-to-a-long-random-value"
DEV_CREDENTIALS_SECRET_KEY = "dev-local-credentials-key-change-me"

_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})


def is_local_environment(environment: str) -> bool:
    """True for local/test (case-insensitive); false for every other ENVIRONMENT."""
    return environment.strip().lower() in _LOCAL_ENVIRONMENTS


def assert_secrets_safe_for_environment(
    environment: str, jwt_secret: str, credentials_secret_key: str
) -> None:
    """Raise ``ValueError`` if a non-local env still uses a placeholder secret."""
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
