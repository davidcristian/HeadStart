"""Unit tests for the notification target service."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User
from app.notifiers.types import DeliveryResult
from app.schemas.target import TargetCreate, TargetUpdate
from app.services.targets import TargetService


def _pro_user(db_session: Session, email: str = "targets@example.com") -> User:
    user = User(email=email, password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()
    return user


def test_get_missing_target_raises(db_session: Session) -> None:
    user = _pro_user(db_session)
    with pytest.raises(NotFoundError):
        TargetService(db_session).get(999, user.id)


def test_create_lists_and_deletes_target(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)

    target = service.create(
        user.id,
        TargetCreate(name="Ntfy", type="ntfy", config={"topic": "jobs"}),
    )
    assert target.id is not None
    assert service.list_all(user.id) == [target]
    assert service.get(target.id, user.id).name == "Ntfy"

    service.delete(target.id, user.id)
    db_session.flush()
    assert service.list_all(user.id) == []


def test_create_rejects_unknown_type(db_session: Session) -> None:
    user = _pro_user(db_session)
    with pytest.raises(ValidationError, match="Unknown target type"):
        TargetService(db_session).create(
            user.id, TargetCreate(name="Bad", type="carrier-pigeon", config={})
        )


def test_update_changes_name_only(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(user.id, TargetCreate(name="Old", type="ntfy", config={}))

    updated = service.update(target.id, user.id, TargetUpdate(name="New"))
    assert updated.name == "New"
    assert updated.type == "ntfy"


def test_update_changes_type_revalidates(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(user.id, TargetCreate(name="Chan", type="ntfy", config={}))

    updated = service.update(target.id, user.id, TargetUpdate(type="slack"))
    assert updated.type == "slack"


def test_update_rejects_unknown_type(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(user.id, TargetCreate(name="Chan", type="ntfy", config={}))

    with pytest.raises(ValidationError, match="Unknown target type"):
        service.update(target.id, user.id, TargetUpdate(type="nope"))


def test_send_test_uses_notifier(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(user.id, TargetCreate(name="Chan", type="ntfy", config={"topic": "t"}))

    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [DeliveryResult(external_id="test", status="sent")]
    with patch("app.services.targets.get_notifier", return_value=mock_notifier):
        result = service.send_test(target.id, user.id)

    assert result.status == "sent"
    ctx, postings = mock_notifier.send.call_args.args
    assert ctx.target_type == "ntfy"
    assert postings[0].external_id == "test"
