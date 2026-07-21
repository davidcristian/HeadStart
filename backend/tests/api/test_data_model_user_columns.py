"""Regression: data-model.md user table lists token_version + AI prefs."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_MODEL_DOC = _REPO_ROOT / "docs" / "modules" / "data-model.md"
_USER_MODEL = _REPO_ROOT / "backend" / "app" / "models" / "user.py"

# Columns the user entity table must document. feed_token_version is already
# present and both version columns stay documented together.
_REQUIRED_USER_COLUMNS = (
    "token_version",
    "summary_provider",
    "summary_api_key_ciphertext",
    "ai_purpose_providers",
    "ai_purpose_models",
)


def _user_entity_table(text: str) -> str:
    """Return the markdown table under ``### user`` (before the next heading)."""
    start = text.index("### user")
    rest = text[start:]
    next_heading = rest.find("\n### ", 1)
    return rest if next_heading < 0 else rest[:next_heading]


def test_data_model_md_user_table_lists_token_and_ai_columns() -> None:
    """Canonical schema doc must include session-revocation and AI preference cols."""
    table = _user_entity_table(_DATA_MODEL_DOC.read_text(encoding="utf-8"))
    for column in _REQUIRED_USER_COLUMNS:
        assert f"| {column} " in table or f"| {column}|" in table, column


def test_user_model_still_defines_doc17_columns() -> None:
    """Guard against doc-only drift if the ORM drops a documented column."""
    src = _USER_MODEL.read_text(encoding="utf-8")
    for column in _REQUIRED_USER_COLUMNS:
        assert f"{column}:" in src, column
