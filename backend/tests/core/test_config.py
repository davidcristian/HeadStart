import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_trusted_proxy_cidrs_parses_and_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUT-17: TRUSTED_PROXY_CIDRS accepts CSV CIDRs and rejects junk at boot."""
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8, 2001:db8::/32")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.trusted_proxy_cidrs == ["10.0.0.0/8", "2001:db8::/32"]

    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "not-a-cidr")
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_CIDRS"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_cors_origins_accepts_list_default() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert isinstance(settings.cors_origins, list)


def test_placeholder_secrets_rejected_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-local deployment must not boot with the dev placeholder secrets."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    message = str(exc_info.value)
    assert "JWT_SECRET" in message
    assert "CREDENTIALS_SECRET_KEY" in message


def test_placeholder_secrets_allowed_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """local/test environments keep the convenient defaults."""
    monkeypatch.setenv("ENVIRONMENT", "local")
    assert Settings(_env_file=None).environment == "local"  # type: ignore[call-arg]


def test_real_secrets_pass_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overriding secrets + SMTP + ntfy topic lets a non-local deployment start normally."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
    assert Settings(_env_file=None).environment == "production"  # type: ignore[call-arg]


def test_http_frontend_with_secure_cookie_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUT-13: Secure refresh cookie + http FRONTEND_BASE_URL must fail fast outside local."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://app.example.com")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "AUTH_COOKIE_SECURE" in str(exc_info.value)
    assert "FRONTEND_BASE_URL" in str(exc_info.value)


def test_http_frontend_with_insecure_cookie_allowed_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP ALB deploys (XCT-15) keep AUTH_COOKIE_SECURE=false with an http frontend."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://alb.example.com")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.auth_cookie_secure is False


def test_samesite_none_without_secure_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUT-13: SameSite=None without Secure is rejected outside local/test."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "None")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "AUTH_COOKIE_SAMESITE" in str(exc_info.value)


def test_samesite_none_with_secure_https_allowed_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SameSite=None is valid when Secure is set and the frontend is https."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "none")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.auth_cookie_samesite == "none"
    assert settings.auth_cookie_secure is True


def test_smtp_host_required_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-local boots must set SMTP_HOST so reset/verify tokens are never logged (AUT-01)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "SMTP_HOST" in str(exc_info.value)


def test_blank_smtp_host_rejected_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whitespace-only SMTP_HOST counts as unset outside local/test."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "   ")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "SMTP_HOST" in str(exc_info.value)


def test_default_credentials_key_rejected_even_with_real_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two secrets are checked independently: a real JWT does not excuse the default key."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    msg = exc_info.value.errors()[0]["msg"]
    assert "CREDENTIALS_SECRET_KEY" in msg
    assert "JWT_SECRET" not in msg


def test_default_jwt_secret_rejected_even_with_real_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror case: a real credentials key does not excuse the default JWT secret."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    msg = exc_info.value.errors()[0]["msg"]
    assert "JWT_SECRET" in msg
    assert "CREDENTIALS_SECRET_KEY" not in msg


@pytest.mark.parametrize("env_value", ["local", "LOCAL", "Local", " local ", "test", "TEST"])
def test_local_environment_variants_keep_placeholder_defaults(
    monkeypatch: pytest.MonkeyPatch, env_value: str
) -> None:
    """Casing/whitespace still counts as local/test (strip().lower() normalization)."""
    monkeypatch.setenv("ENVIRONMENT", env_value)
    assert Settings(_env_file=None).environment == env_value  # type: ignore[call-arg]


def test_derived_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("REDIS_HOST", "redis")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.sqlalchemy_url.startswith("postgresql+psycopg://")
    assert "db:5432" in settings.sqlalchemy_url
    assert settings.broker_url == "redis://redis:6379/0"
    assert settings.result_backend == "redis://redis:6379/1"


def test_redis_tls_auth_builds_rediss_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPS-10: ElastiCache AUTH + TLS → rediss:// with URL-encoded password."""
    monkeypatch.setenv("REDIS_HOST", "cache.example")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss/word")
    monkeypatch.setenv("REDIS_TLS", "true")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (
        settings.broker_url == "rediss://:p%40ss%2Fword@cache.example:6379/0?ssl_cert_reqs=required"
    )
    assert (
        settings.result_backend
        == "rediss://:p%40ss%2Fword@cache.example:6379/1?ssl_cert_reqs=required"
    )


def test_celery_broker_url_overrides_derived(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit CELERY_BROKER_URL wins over REDIS_* derivation."""
    monkeypatch.setenv("REDIS_HOST", "ignored")
    monkeypatch.setenv("CELERY_BROKER_URL", "rediss://:tok@broker:6380/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "rediss://:tok@broker:6380/1")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.broker_url == "rediss://:tok@broker:6380/0"
    assert settings.result_backend == "rediss://:tok@broker:6380/1"


def test_database_url_overrides_derived(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit DATABASE_URL takes precedence over the derived Postgres URL."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.sqlalchemy_url == "sqlite+pysqlite:///:memory:"


def test_short_credentials_key_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-placeholder but short CREDENTIALS_SECRET_KEY fails the AUT-05 length floor."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "too-short-to-be-safe")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "jobs-a1b2c3d4e5f67890")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "CREDENTIALS_SECRET_KEY" in str(exc_info.value)
    assert "at least 32" in str(exc_info.value)


def test_placeholder_ntfy_topic_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-local boots must override the guessable ntfy default topic (OPS-16)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "NTFY_DEFAULT_TOPIC" in str(exc_info.value)


def test_blank_ntfy_topic_rejected_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whitespace-only NTFY_DEFAULT_TOPIC counts as unset outside local/test."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "   ")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "NTFY_DEFAULT_TOPIC" in str(exc_info.value)


def test_change_me_ntfy_topic_rejected_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any topic containing change-me is rejected outside local/test."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "my-topic-change-me-please")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "NTFY_DEFAULT_TOPIC" in str(exc_info.value)


def test_samesite_normalizer_passes_through_non_string() -> None:
    """The SameSite validator only lowercases strings; other types pass unchanged."""
    from app.core.trusted_proxies import normalize_samesite

    assert normalize_samesite(None) is None
    assert normalize_samesite(123) == 123
    assert Settings._normalize_samesite("Lax") == "lax"


def test_log_format_defaults_to_json() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.log_format == "json"


def test_log_format_normalizes_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", " TEXT ")
    assert Settings(_env_file=None).log_format == "text"  # type: ignore[call-arg]


def test_log_format_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", "yaml")
    with pytest.raises(ValidationError, match="LOG_FORMAT"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_parse_log_format_rejects_non_string() -> None:
    from app.core.log_format import parse_log_format

    with pytest.raises(TypeError, match="LOG_FORMAT"):
        parse_log_format(None)
    with pytest.raises(TypeError, match="LOG_FORMAT"):
        parse_log_format(1)


def test_parse_csv_list_and_validate_trusted_proxy_cidrs() -> None:
    from app.core.trusted_proxies import parse_csv_list, validate_trusted_proxy_cidrs

    assert parse_csv_list("10.0.0.0/8, 192.168.0.0/16") == ["10.0.0.0/8", "192.168.0.0/16"]
    assert parse_csv_list(["10.0.0.0/8"]) == ["10.0.0.0/8"]
    assert validate_trusted_proxy_cidrs(["10.0.0.0/8"]) == ["10.0.0.0/8"]
    with pytest.raises(ValueError, match="TRUSTED_PROXY_CIDRS"):
        validate_trusted_proxy_cidrs(["nope"])


def test_inbox_poll_interval_comment_has_no_edit_artifact() -> None:
    """AUT-11: Settings comment must say 'new message classification', not an Edit leftover."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "app" / "core" / "config.py"
    text = source.read_text(encoding="utf-8")
    assert "new_string" not in text
    assert "old_string" not in text
    assert "# How often beat polls mailboxes for new message classification (seconds)." in text


def test_billing_currency_defaults_to_eur() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.billing_currency == "eur"


def test_billing_currency_normalizes_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BILLING_CURRENCY", " USD ")
    assert Settings(_env_file=None).billing_currency == "usd"  # type: ignore[call-arg]


def test_billing_currency_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BILLING_CURRENCY", "euro")
    with pytest.raises(ValidationError, match="BILLING_CURRENCY"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_normalize_billing_currency_passes_non_string() -> None:
    assert Settings._normalize_billing_currency(None) is None
    assert Settings._normalize_billing_currency(12) == 12
