"""Unit tests for the notification target service."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User
from app.notifiers.types import DeliveryResult
from app.schemas.target import TargetCreate, TargetUpdate
from app.services.targets import TargetService

_SAFE_TOPIC = "jobs-a1b2c3d4e5f67890"


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
        TargetCreate(name="Ntfy", type="ntfy", config={"topic": _SAFE_TOPIC}),
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


def test_create_rejects_guessable_ntfy_topic(db_session: Session) -> None:
    """NTF-06: placeholder / short topics must not become live targets."""
    user = _pro_user(db_session)
    service = TargetService(db_session)
    for topic in ("headstart-change-me", "jobs", "my-topic-change-me", ""):
        with pytest.raises(ValidationError, match="unguessable"):
            service.create(
                user.id,
                TargetCreate(name="Bad ntfy", type="ntfy", config={"topic": topic}),
            )


def test_update_rejects_guessable_ntfy_topic(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Ok", type="ntfy", config={"topic": _SAFE_TOPIC})
    )
    with pytest.raises(ValidationError, match="unguessable"):
        service.update(
            target.id,
            user.id,
            TargetUpdate(config={"topic": "headstart-change-me"}),
        )


def test_update_changes_name_only(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Old", type="ntfy", config={"topic": _SAFE_TOPIC})
    )

    updated = service.update(target.id, user.id, TargetUpdate(name="New"))
    assert updated.name == "New"
    assert updated.type == "ntfy"


def test_update_changes_type_revalidates(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Chan", type="ntfy", config={"topic": _SAFE_TOPIC})
    )

    updated = service.update(
        target.id,
        user.id,
        TargetUpdate(
            type="slack",
            config={"webhook_url": "https://hooks.example/services/T00/B00/xxxx"},
        ),
    )
    assert updated.type == "slack"


def test_update_type_without_matching_config_rejects(db_session: Session) -> None:
    """API-14: changing type re-validates the existing config against the new type."""
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Chan", type="ntfy", config={"topic": _SAFE_TOPIC})
    )
    with pytest.raises(ValidationError, match="config.webhook_url"):
        service.update(target.id, user.id, TargetUpdate(type="slack"))


def test_create_rejects_private_webhook_url(db_session: Session) -> None:
    user = _pro_user(db_session)
    with pytest.raises(ValidationError, match="safe outbound URL"):
        TargetService(db_session).create(
            user.id,
            TargetCreate(
                name="Hook",
                type="webhook",
                config={"webhook_url": "http://127.0.0.1/hook"},
            ),
        )


def test_create_email_target(db_session: Session) -> None:
    user = _pro_user(db_session)
    target = TargetService(db_session).create(
        user.id, TargetCreate(name="Mail", type="email", config={"to": "a@example.com"})
    )
    assert target.type == "email"


def test_update_non_dict_config_falls_back_to_empty(db_session: Session) -> None:
    """Defensive: non-dict stored config is treated as {} for re-validation."""
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Ok", type="ntfy", config={"topic": _SAFE_TOPIC})
    )
    target.config = ["not", "a", "dict"]  # type: ignore[assignment]
    db_session.flush()
    with pytest.raises(ValidationError, match="unguessable"):
        service.update(target.id, user.id, TargetUpdate(name="Still"))


def test_update_rejects_unknown_type(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Chan", type="ntfy", config={"topic": _SAFE_TOPIC})
    )

    with pytest.raises(ValidationError, match="Unknown target type"):
        service.update(target.id, user.id, TargetUpdate(type="nope"))


def test_send_test_uses_notifier(db_session: Session) -> None:
    user = _pro_user(db_session)
    service = TargetService(db_session)
    target = service.create(
        user.id, TargetCreate(name="Chan", type="ntfy", config={"topic": _SAFE_TOPIC})
    )

    mock_notifier = MagicMock()
    mock_notifier.send.return_value = [DeliveryResult(external_id="test", status="sent")]
    with patch("app.services.targets.get_notifier", return_value=mock_notifier):
        result = service.send_test(target.id, user.id)

    assert result.status == "sent"
    ctx, postings = mock_notifier.send.call_args.args
    assert ctx.target_type == "ntfy"
    assert postings[0].external_id == "test"
