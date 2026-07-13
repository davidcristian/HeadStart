"""Regression: inbox_reply_send_log empty-string cols have DB defaults (DAT-08)."""

from __future__ import annotations

import re
from pathlib import Path

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"
_CREATE = _VERSIONS / "20260703_0031_inbox_reply_send_log.py"
_ALTER = _VERSIONS / "20260713_0045_reply_send_log_defaults.py"

_COLS = ("reason", "subject", "body_excerpt")


def test_create_migration_sets_server_default_on_empty_text_cols() -> None:
    """Fresh installs must match inbox_classification's server_default=''."""
    text = _CREATE.read_text(encoding="utf-8")
    for col in _COLS:
        pattern = rf'Column\(\s*"{col}".*?server_default\s*=\s*""'
        assert re.search(pattern, text, re.S), f"0031 must set server_default='' on {col}"


def test_followup_migration_alters_existing_dbs() -> None:
    """DBs that already applied 0031 still get the defaults via alter_column."""
    text = _ALTER.read_text(encoding="utf-8")
    assert 'revision: str = "0045_reply_send_defaults"' in text
    assert 'down_revision: str | None = "0044_token_used_at"' in text
    assert 'op.alter_column(_TABLE, column, server_default="")' in text
    for col in _COLS:
        assert f'"{col}"' in text or f"'{col}'" in text
