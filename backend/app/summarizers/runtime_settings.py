"""Per-user overrides layered on global summary settings."""

from app.ai.runtime_settings import (
    USER_AI_PROVIDERS,
    resolve_ai_settings,
    resolve_summary_settings,
)

# Backward-compatible alias for existing imports.
USER_SUMMARY_PROVIDERS = USER_AI_PROVIDERS

__all__ = [
    "USER_AI_PROVIDERS",
    "USER_SUMMARY_PROVIDERS",
    "resolve_ai_settings",
    "resolve_summary_settings",
]
