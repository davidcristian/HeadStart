"""Application settings, loaded from environment variables.

This is the single place that reads configuration. Everything else imports the
`settings` singleton; nothing else should touch `os.environ`.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- general ----
    environment: str = "local"
    log_level: str = "INFO"

    # ---- api ----
    # NoDecode: keep pydantic-settings from JSON-parsing the env var so our
    # validator can accept a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    # ---- auth (JWT) ----
    # Secret used to sign access/refresh JWTs. MUST be overridden in any
    # non-local deployment; a stable random value keeps sessions valid across
    # restarts.
    jwt_secret: str = "dev-local-jwt-secret-change-me-to-a-long-random-value"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ---- credential encryption ----
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt per-site
    # credentials at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    credentials_secret_key: str = "dev-local-credentials-key-change-me"

    # ---- database ----
    postgres_user: str = "jobnotifier"
    postgres_password: str = "jobnotifier"
    postgres_db: str = "jobnotifier"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # ---- redis / celery ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # ---- scheduler ----
    scheduler_tick_seconds: int = 30
    scheduler_max_catchup: int = 1

    # ---- ntfy defaults (used by seed + default target) ----
    ntfy_default_server_url: str = "https://ntfy.sh"
    ntfy_default_topic: str = "jobnotifier-change-me"

    # ---- seed (local demo account that owns the example data) ----
    seed_user_email: str = "demo@example.com"
    seed_user_password: str = "demo-password-change-me"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow CORS origins as a comma-separated string in the environment."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or f"redis://{self.redis_host}:{self.redis_port}/0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or f"redis://{self.redis_host}:{self.redis_port}/1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
