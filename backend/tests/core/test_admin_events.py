"""Tests for structured admin mutation audit logging."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.admin_events import log_admin_user_update
from app.models.user import User
from app.schemas.admin import AdminUserUpdate
from app.services.admin import AdminService


def test_log_admin_user_update_emits_before_after(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="app.core.admin_events"):
        log_admin_user_update(
            actor_id=1,
            target_id=2,
            before={"is_active": True, "is_admin": False, "plan": "free"},
            after={"is_active": False, "is_admin": True, "plan": "pro"},
        )
    assert len(caplog.records) == 1
    record = caplog.records[0]
    message = record.getMessage()
    assert "admin_event=user_update" in message
    assert "actor_id=1" in message
    assert "target_id=2" in message
    assert "before=is_active=true,is_admin=false,plan=free" in message
    assert "after=is_active=false,is_admin=true,plan=pro" in message
    assert record.admin_event == "user_update"
    assert record.actor_id == 1
    assert record.target_id == 2
    assert record.before == {"is_active": True, "is_admin": False, "plan": "free"}
    assert record.after == {"is_active": False, "is_admin": True, "plan": "pro"}


def test_log_admin_user_update_skips_noop(caplog: pytest.LogCaptureFixture) -> None:
    flags = {"is_active": True, "is_admin": False, "plan": "free"}
    with caplog.at_level("INFO", logger="app.core.admin_events"):
        log_admin_user_update(actor_id=1, target_id=2, before=flags, after=flags)
    assert caplog.records == []


def test_log_admin_user_update_only_changed_fields(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="app.core.admin_events"):
        log_admin_user_update(
            actor_id=9,
            target_id=4,
            before={"is_active": True, "is_admin": False, "plan": "free"},
            after={"is_active": True, "is_admin": False, "plan": "plus"},
        )
    record = caplog.records[0]
    message = record.getMessage()
    assert "before=plan=free" in message
    assert "after=plan=plus" in message
    assert "is_active" not in message
    assert "is_admin" not in message
    assert record.before == {"plan": "free"}
    assert record.after == {"plan": "plus"}


def test_update_user_logs_admin_audit(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    target = User(
        email="member@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        plan="free",
    )
    db_session.add_all([admin, target])
    db_session.flush()

    with caplog.at_level("INFO", logger="app.core.admin_events"):
        AdminService(db_session).update_user(
            target.id,
            actor_id=admin.id,
            data=AdminUserUpdate(is_active=False, is_admin=True, plan="pro"),
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any("admin_event=user_update" in message for message in messages)
    audit = next(message for message in messages if "admin_event=user_update" in message)
    assert f"actor_id={admin.id}" in audit
    assert f"target_id={target.id}" in audit
    assert "before=is_active=true,is_admin=false,plan=free" in audit
    assert "after=is_active=false,is_admin=true,plan=pro" in audit


def test_update_user_noop_patch_skips_audit(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    admin = User(email="admin@example.com", password_hash="x", is_admin=True, is_active=True)
    target = User(
        email="member@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
        plan="free",
    )
    db_session.add_all([admin, target])
    db_session.flush()

    with caplog.at_level("INFO", logger="app.core.admin_events"):
        AdminService(db_session).update_user(
            target.id,
            actor_id=admin.id,
            data=AdminUserUpdate(is_active=True, is_admin=False, plan="free"),
        )

    assert not any("admin_event=user_update" in r.getMessage() for r in caplog.records)
