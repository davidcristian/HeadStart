import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


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
    """Overriding both secrets lets a non-local deployment start normally."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-long-random-production-secret-value")
    monkeypatch.setenv("CREDENTIALS_SECRET_KEY", "another-real-production-fernet-value")
    assert Settings(_env_file=None).environment == "production"  # type: ignore[call-arg]


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
