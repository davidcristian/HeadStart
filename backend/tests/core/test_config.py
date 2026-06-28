import pytest

from app.core.config import Settings


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_accepts_list_default() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert isinstance(settings.cors_origins, list)


def test_derived_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("REDIS_HOST", "redis")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.sqlalchemy_url.startswith("postgresql+psycopg://")
    assert "db:5432" in settings.sqlalchemy_url
    assert settings.broker_url == "redis://redis:6379/0"
    assert settings.result_backend == "redis://redis:6379/1"
