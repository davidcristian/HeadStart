"""Regression: test SQLite engines enforce foreign keys (TST-01 / DAT-07)."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def test_db_session_enables_sqlite_foreign_keys(db_session: Session) -> None:
    """conftest connect listener must turn PRAGMA foreign_keys on for every engine."""
    assert db_session.scalar(text("PRAGMA foreign_keys")) == 1
