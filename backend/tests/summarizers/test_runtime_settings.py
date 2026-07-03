"""The summarizer runtime_settings module re-exports the shared AI helpers."""

from app.ai.runtime_settings import (
    USER_AI_PROVIDERS,
    resolve_ai_settings,
    resolve_summary_settings,
)
from app.summarizers import runtime_settings


def test_runtime_settings_reexports_shared_helpers() -> None:
    assert runtime_settings.USER_AI_PROVIDERS is USER_AI_PROVIDERS
    assert runtime_settings.USER_SUMMARY_PROVIDERS is USER_AI_PROVIDERS
    assert runtime_settings.resolve_ai_settings is resolve_ai_settings
    assert runtime_settings.resolve_summary_settings is resolve_summary_settings
    assert set(runtime_settings.__all__) == {
        "USER_AI_PROVIDERS",
        "USER_SUMMARY_PROVIDERS",
        "resolve_ai_settings",
        "resolve_summary_settings",
    }
