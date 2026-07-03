"""Tests for FastAPI dependencies (session lifecycle + auth guards)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.api import deps


def test_get_db_commits_on_success() -> None:
    session = MagicMock()
    with patch.object(deps, "SessionFactory", return_value=session):
        gen = deps.get_db()
        yielded = next(gen)
        assert yielded is session
        with pytest.raises(StopIteration):
            next(gen)  # exhaust to trigger the commit + close

    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    session.close.assert_called_once()


def test_get_db_rolls_back_on_error() -> None:
    session = MagicMock()
    with patch.object(deps, "SessionFactory", return_value=session):
        gen = deps.get_db()
        next(gen)
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("boom"))

    session.commit.assert_not_called()
    session.rollback.assert_called_once()
    session.close.assert_called_once()
