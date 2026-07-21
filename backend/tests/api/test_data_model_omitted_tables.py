"""Regression: data-model.md documents artifact/promo/GDPR tables."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_MODEL_DOC = _REPO_ROOT / "docs" / "modules" / "data-model.md"
_MODELS_DIR = _REPO_ROOT / "backend" / "app" / "models"

# Entity headings data-model.md must document (registration_lock was already
# documented; inbox_* stay in inbox.md per the ownership note).
_REQUIRED_ENTITY_HEADINGS = (
    "### application_artifact",
    "### promo_code",
    "### promo_redemption",
    "### promo_validation_attempt",
    "### data_request_log",
)

_REQUIRED_MODEL_FILES = (
    "application_artifact.py",
    "promo_code.py",
    "promo_redemption.py",
    "promo_validation_attempt.py",
    "data_request_log.py",
)


def _application_log_entity_table(text: str) -> str:
    """Return the markdown table under ``### application_log``."""
    start = text.index("### application_log")
    rest = text[start:]
    next_heading = rest.find("\n### ", 1)
    return rest if next_heading < 0 else rest[:next_heading]


def test_data_model_md_lists_artifact_promo_and_gdpr_tables() -> None:
    """Canonical schema doc must cover user-owned artifact/billing/GDPR tables."""
    text = _DATA_MODEL_DOC.read_text(encoding="utf-8")
    for heading in _REQUIRED_ENTITY_HEADINGS:
        assert heading in text, heading
    assert "Inbox / mailbox tables" in text
    assert "inbox.md" in text


def test_application_log_table_lists_tailored_resume_artifact_fk() -> None:
    """application_log docs must include the tailored resume artifact FK."""
    table = _application_log_entity_table(_DATA_MODEL_DOC.read_text(encoding="utf-8"))
    assert "tailored_resume_artifact_id" in table


def test_orm_models_still_define_doc19_tables() -> None:
    """Guard against doc-only drift if an ORM module is removed."""
    for name in _REQUIRED_MODEL_FILES:
        assert (_MODELS_DIR / name).is_file(), name
    app_log = (_MODELS_DIR / "application_log.py").read_text(encoding="utf-8")
    assert "tailored_resume_artifact_id" in app_log
