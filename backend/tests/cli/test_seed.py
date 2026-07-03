"""Tests for the `make seed` example-data script."""

from __future__ import annotations

import runpy
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import seed as seed_module
from app.cli.seed import main, seed
from app.core.config import settings
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.source import Source
from app.models.user import User


@pytest.fixture
def seed_scope(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """Point the seed script at the in-memory test session."""

    @contextmanager
    def _scope() -> Iterator[Session]:
        yield db_session
        db_session.commit()

    monkeypatch.setattr(seed_module, "session_scope", _scope)
    return db_session


def test_seed_creates_demo_account_and_example_data(seed_scope: Session) -> None:
    seed()

    email = settings.seed_user_email.lower()
    user = seed_scope.scalar(select(User).where(User.email == email))
    assert user is not None
    # First account becomes admin.
    assert user.is_admin is True
    assert user.email_verified_at is not None

    target = seed_scope.scalar(
        select(NotificationTarget).where(NotificationTarget.name == "Default ntfy")
    )
    assert target is not None
    assert target.type == "ntfy"
    assert target.config["topic"] == settings.ntfy_default_topic

    source = seed_scope.scalar(select(Source).where(Source.name == "Example (Greenhouse)"))
    assert source is not None
    assert source.adapter_key == "greenhouse"

    search = seed_scope.scalar(select(Search).where(Search.name == "Example - all jobs"))
    assert search is not None
    assert search.enabled is False


def test_seed_is_idempotent(seed_scope: Session) -> None:
    seed()
    seed()  # Second run must not duplicate any rows.

    email = settings.seed_user_email.lower()
    assert len(list(seed_scope.scalars(select(User).where(User.email == email)))) == 1
    assert len(list(seed_scope.scalars(select(NotificationTarget)))) == 1
    assert len(list(seed_scope.scalars(select(Source)))) == 1
    assert len(list(seed_scope.scalars(select(Search)))) == 1


def test_seed_is_not_admin_when_other_users_exist(seed_scope: Session) -> None:
    """A pre-existing user means the demo account is not the bootstrap admin."""
    seed_scope.add(User(email="first@example.com", password_hash="x"))
    seed_scope.flush()

    seed()

    demo = seed_scope.scalar(select(User).where(User.email == settings.seed_user_email.lower()))
    assert demo is not None
    assert demo.is_admin is False


def test_seed_verifies_existing_unverified_user(seed_scope: Session) -> None:
    """An existing seed user with no verification timestamp gets verified."""
    seed_scope.add(
        User(
            email=settings.seed_user_email.lower(),
            password_hash="x",
            email_verified_at=None,
        )
    )
    seed_scope.flush()

    seed()

    demo = seed_scope.scalar(select(User).where(User.email == settings.seed_user_email.lower()))
    assert demo is not None
    assert demo.email_verified_at is not None


def test_main_invokes_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr(seed_module, "seed", lambda: called.append(True))
    main()
    assert called == [True]


def test_module_entrypoint_runs_seed(db_session: Session) -> None:
    """Executing the module as a script (`python -m app.cli.seed`) calls seed().

    runpy re-executes the module in a fresh namespace, so patch the db helper it
    binds at import time rather than the already-imported module's `seed`.
    """

    @contextmanager
    def _scope() -> Iterator[Session]:
        yield db_session
        db_session.commit()

    with patch("app.core.db.session_scope", _scope):
        runpy.run_module("app.cli.seed", run_name="__main__")

    demo = db_session.scalar(select(User).where(User.email == settings.seed_user_email.lower()))
    assert demo is not None
