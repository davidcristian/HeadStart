"""Application settings, loaded from environment variables.

This is the single place that reads configuration. Everything else imports the
`settings` singleton; nothing else should touch `os.environ`.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core import secret_policy
from app.core.feature_flags import stripe_billing_configured
from app.core.log_format import parse_log_format
from app.core.redis_url import redis_url_from_settings
from app.core.trusted_proxies import CsvStrList, TrustedProxyCidrs, normalize_samesite


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
    # json (default) for CloudWatch/Loki; text for local grepping (AUT-16).
    log_format: Annotated[str, BeforeValidator(parse_log_format)] = "json"
    # ---- api ----
    cors_origins: CsvStrList = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    # Empty = ignore XFF. ECS sets VPC CIDR so ALB client IPs are trusted (AUT-17).
    trusted_proxy_cidrs: TrustedProxyCidrs = []

    # ---- auth (JWT) ----
    # Stable random JWT secret; rejected outside local/test — see core/secret_policy.py.
    jwt_secret: str = secret_policy.DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    # RSS feed JWTs travel in ?token= URLs; keep far shorter than a decade (AUT-22).
    feed_token_expire_days: int = 90
    password_reset_expire_minutes: int = 60
    email_verification_expire_minutes: int = 1440  # 24 hours
    frontend_base_url: str = "http://localhost:5173"

    # ---- auth refresh cookie ----
    # httpOnly refresh cookie (XSS-safe). Prod defaults Secure+Lax; local HTTP: SECURE=false.
    auth_cookie_name: str = "headstart_refresh"
    auth_cookie_path: str = "/api/v1/auth"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"

    @field_validator("auth_cookie_samesite", mode="before")
    @classmethod
    def _normalize_samesite(cls, value: object) -> object:
        return normalize_samesite(value)

    # ---- email (password reset + email notifier) ----
    # Empty SMTP_HOST is local/test-only (links logged); required elsewhere (AUT-01).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@headstart.local"
    smtp_use_tls: bool = True

    # ---- credential encryption ----
    # scrypt → Fernet (core/crypto.py). Non-local length >= MIN_CREDENTIALS_SECRET_KEY_LEN.
    credentials_secret_key: str = secret_policy.DEV_CREDENTIALS_SECRET_KEY
    credentials_secret_key_previous: str = ""  # MultiFernet rotation

    profile_resume_max_bytes: int = 2_097_152
    profile_resume_template_max_bytes: int = 524_288
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
    redis_password: str = ""  # ElastiCache AUTH; empty for local docker Redis
    redis_tls: bool = False  # rediss:// when true (required with AUTH — OPS-10)
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # ---- scheduler ----
    scheduler_tick_seconds: int = 30

    # ---- playwright (worker / opt-in scraper) ----
    playwright_navigation_timeout_ms: int = 30_000
    playwright_max_retries: int = 1  # retries after first attempt; 0 = none
    scraper_max_response_bytes: int = 5_242_880  # SCR-04 HTTP body cap

    # ---- metrics (Prometheus) ----
    metrics_enabled: bool = True
    metrics_port: int = 9090  # worker /metrics bind
    metrics_token: str = ""  # empty = unauthenticated

    # ---- AI summaries ("why this matches" blurb in notifications) ----
    summaries_enabled: bool = True
    # heuristic | openai | gemini | anthropic | llamacpp
    summary_provider: str = "heuristic"
    summary_max_chars: int = 280

    # ---- AI cover letters / resume curation ----
    cover_letters_enabled: bool = True
    cover_letter_max_chars: int = 4000
    cover_letter_max_tokens: int = 900
    resume_curation_enabled: bool = True
    resume_curation_max_tokens: int = 1200
    resume_compile_timeout_seconds: float = 60.0

    # ---- AI inbox classification / reply drafting (dev) ----
    email_classify_max_body_chars: int = 8000
    email_classify_max_tokens: int = 256
    reply_drafts_enabled: bool = True
    email_draft_max_chars: int = 4000
    email_draft_max_tokens: int = 600

    # ---- OpenAI / Gemini / Anthropic / llama.cpp ----
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_api_version: str = "2023-06-01"
    llamacpp_base_url: str = "http://localhost:8080/v1"
    llamacpp_model: str = "local"
    llamacpp_api_key: str = ""

    # ---- ntfy defaults (seed demo target) ----
    ntfy_default_server_url: str = "https://ntfy.sh"
    ntfy_default_topic: str = secret_policy.DEV_NTFY_DEFAULT_TOPIC

    # ---- free-tier ads ----
    ads_enabled: bool = True
    ads_external_slot_url: str = ""  # HTTPS iframe; empty = upgrade CTA only

    # ---- inbox agent (dev-only; Phase 20c mailbox connector) ----
    inbox_agent_enabled: bool = False
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
    gmail_oauth_client_id: str = ""
    gmail_oauth_client_secret: str = ""
    gmail_oauth_redirect_uri: str = ""
    outlook_oauth_client_id: str = ""
    outlook_oauth_client_secret: str = ""
    outlook_oauth_redirect_uri: str = ""
    yahoo_oauth_client_id: str = ""
    yahoo_oauth_client_secret: str = ""
    yahoo_oauth_redirect_uri: str = ""
    inbox_ghost_window_days: int = 14
    inbox_ghost_check_interval_seconds: int = 3600
    inbox_poll_interval_seconds: int = 300
    inbox_poll_batch_size: int = 50
    inbox_reply_min_delay_seconds: int = 1800
    inbox_reply_delay_jitter_seconds: int = 900
    inbox_reply_send_interval_seconds: int = 60
    inbox_reply_max_per_hour: int = 10
    inbox_reply_max_per_day: int = 30

    # ---- Stripe billing (optional; empty disables paid checkout) ----
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_monthly: str = ""
    stripe_price_starter_annual: str = ""
    stripe_price_plus_monthly: str = ""
    stripe_price_plus_annual: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_annual: str = ""
    stripe_trial_days: int = 14

    # ---- seed (local demo account) ----
    seed_user_email: str = "demo@example.com"
    seed_user_password: str = "demo-password-change-me"

    @model_validator(mode="after")
    def _reject_placeholder_secrets_outside_local(self) -> "Settings":
        """Refuse non-local boots with placeholder secrets / SMTP / ntfy / cookie drift."""
        secret_policy.assert_boot_safe_for_environment(
            self.environment,
            self.jwt_secret,
            self.credentials_secret_key,
            self.smtp_host,
            self.ntfy_default_topic,
            auth_cookie_secure=self.auth_cookie_secure,
            auth_cookie_samesite=self.auth_cookie_samesite,
            frontend_base_url=self.frontend_base_url,
        )
        return self

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
        return self.celery_broker_url or redis_url_from_settings(self, 0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or redis_url_from_settings(self, 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def billing_enabled(self) -> bool:
        """True when Stripe keys and all paid-tier price IDs are configured."""
        return stripe_billing_configured(self)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
