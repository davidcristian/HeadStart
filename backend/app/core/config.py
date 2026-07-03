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
    password_reset_expire_minutes: int = 60
    email_verification_expire_minutes: int = 1440  # 24 hours
    # Base URL of the web UI (used in password-reset and verification links).
    frontend_base_url: str = "http://localhost:5173"

    # ---- auth refresh cookie ----
    # The refresh token is delivered as an httpOnly cookie (never readable by JS,
    # so it is out of reach of XSS). Scope it to the auth endpoints. Defaults are
    # production-safe (Secure + Lax, same-site behind nginx); over plain-HTTP
    # local dev set AUTH_COOKIE_SECURE=false.
    auth_cookie_name: str = "headstart_refresh"
    auth_cookie_path: str = "/api/v1/auth"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"

    @field_validator("auth_cookie_samesite", mode="before")
    @classmethod
    def _normalize_samesite(cls, value: object) -> object:
        """SameSite is case-insensitive; Starlette expects a lowercase literal."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    # ---- email (password reset + email notifier) ----
    # Leave SMTP_HOST empty in local dev; reset links are logged instead.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@headstart.local"
    smtp_use_tls: bool = True

    # ---- credential encryption ----
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt per-site
    # credentials at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    credentials_secret_key: str = "dev-local-credentials-key-change-me"

    # Max resume file size for application-profile uploads (bytes).
    profile_resume_max_bytes: int = 2_097_152
    # Max LaTeX resume template size (bytes).
    profile_resume_template_max_bytes: int = 524_288
    # Max multi-file LaTeX template bundle (.zip) size (bytes).
    profile_resume_template_bundle_max_bytes: int = 2_097_152

    # ---- database ----
    postgres_user: str = "headstart"
    postgres_password: str = "headstart"
    postgres_db: str = "headstart"
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

    # ---- playwright (worker / opt-in scraper) ----
    playwright_navigation_timeout_ms: int = 30_000
    # Retries after the first attempt (0 = no retries).
    playwright_max_retries: int = 1

    # ---- metrics (Prometheus) ----
    metrics_enabled: bool = True
    # Worker-only HTTP port for /metrics when the pipeline runs in Celery.
    metrics_port: int = 9090
    # Optional bearer token for GET /metrics (empty = unauthenticated).
    metrics_token: str = ""

    # ---- AI summaries ("why this matches" blurb in notifications) ----
    # Generate a short blurb per new job and include it in notifications + the
    # Jobs feed. The default provider is offline and free.
    summaries_enabled: bool = True
    # Registered summarizer key: "heuristic" (offline, default), "openai",
    # "gemini", "anthropic", or "llamacpp" (local dev only).
    summary_provider: str = "heuristic"
    # Hard cap on a blurb's length before it is stored/sent.
    summary_max_chars: int = 280

    # ---- AI cover letters (apply dialog; reuses SUMMARY_PROVIDER for Pro users) ----
    cover_letters_enabled: bool = True
    cover_letter_max_chars: int = 4000
    cover_letter_max_tokens: int = 900

    # ---- AI resume curation (LaTeX template → tailored PDF) ----
    resume_curation_enabled: bool = True
    resume_curation_max_tokens: int = 1200
    resume_compile_timeout_seconds: float = 60.0

    # ---- AI inbox email classification (dev-only inbox agent) ----
    email_classify_max_body_chars: int = 8000
    email_classify_max_tokens: int = 256

    # ---- OpenAI (used only when summary_provider = "openai") ----
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # ---- Gemini (used only when summary_provider = "gemini") ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # ---- Anthropic (used only when summary_provider = "anthropic") ----
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_api_version: str = "2023-06-01"

    # ---- llama.cpp (used only when summary_provider = "llamacpp"; local dev) ----
    llamacpp_base_url: str = "http://localhost:8080/v1"
    llamacpp_model: str = "local"
    llamacpp_api_key: str = ""

    # ---- ntfy defaults (used by seed + default target) ----
    ntfy_default_server_url: str = "https://ntfy.sh"
    ntfy_default_topic: str = "headstart-change-me"

    # ---- free-tier ads (optional third-party slot; house upgrade CTA is always on) ----
    # Set ADS_ENABLED=false to hide all in-app ads, including the built-in upgrade card.
    ads_enabled: bool = True
    # HTTPS URL of a hosted ad iframe (e.g. AdSense); shown only when the user accepts
    # optional cookies. Leave empty to show only the built-in upgrade promotion.
    ads_external_slot_url: str = ""

    # ---- inbox agent (dev-only; Phase 20c mailbox connector) ----
    # Disabled by default — do not enable on hosted multi-tenant prod.
    inbox_agent_enabled: bool = False
    # When true, fall back to INBOX_* env vars for every user without saved creds.
    inbox_use_env_credentials: bool = False
    inbox_imap_host: str = ""
    inbox_imap_port: int = 993
    inbox_imap_use_ssl: bool = True
    inbox_imap_user: str = ""
    inbox_imap_password: str = ""
    inbox_imap_mailbox: str = "INBOX"
    inbox_smtp_host: str = ""
    inbox_smtp_port: int = 587
    inbox_smtp_use_tls: bool = True
    inbox_smtp_user: str = ""
    inbox_smtp_password: str = ""
    inbox_smtp_from: str = ""

    # ---- Stripe billing (optional; leave empty to disable paid checkout) ----
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Stripe Price IDs (create in the Stripe Dashboard; must be recurring).
    stripe_price_starter_monthly: str = ""
    stripe_price_starter_annual: str = ""
    stripe_price_plus_monthly: str = ""
    stripe_price_plus_annual: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_annual: str = ""
    # Optional trial length for new Pro subscriptions (days).
    stripe_trial_days: int = 14

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def billing_enabled(self) -> bool:
        """True when Stripe keys and all paid-tier price IDs are configured."""
        return bool(
            self.stripe_secret_key
            and self.stripe_webhook_secret
            and self.stripe_price_starter_monthly
            and self.stripe_price_starter_annual
            and self.stripe_price_plus_monthly
            and self.stripe_price_plus_annual
            and self.stripe_price_pro_monthly
            and self.stripe_price_pro_annual
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
