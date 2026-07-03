"""Service tests for inbox folder routing."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.inbox.types import MoveResult
from app.models.inbox_classification import InboxClassification
from app.models.user import User
from app.schemas.inbox_routing import InboxRouteRequest, InboxRoutingConfigUpdate
from app.schemas.mailbox import MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_routing import (
    InboxRoutingService,
    _provider_message_id_from_classification,
)
from tests.services.test_inbox import _sample_config


def _user(session: Session, email: str = "routing@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


def _credential(session: Session, user_id: int) -> None:
    InboxService(session).upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))


def _classification(
    user_id: int, *, label: str = "rejection", uid: int = 42
) -> InboxClassification:
    return InboxClassification(
        user_id=user_id,
        message_uid=uid,
        label=label,
        confidence=0.9,
        reason="test",
        provider="heuristic",
    )


def test_update_routing_config_persists_on_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    svc = InboxRoutingService(db_session)
    updated = svc.update_config(
        user_id,
        InboxRoutingConfigUpdate(enabled=True, label_folders={"rejection": "Custom/Rejected"}),
    )
    assert updated.enabled is True
    assert updated.label_folders["rejection"] == "Custom/Rejected"
    assert updated.label_folders["general"] == "HeadStart/General"

    read = svc.get_config(user_id)
    assert read.enabled is True
    assert read.label_folders["rejection"] == "Custom/Rejected"


def test_route_classification_moves_message(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))
    row = _classification(user_id)
    db_session.add(row)
    db_session.flush()

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        mock_move.return_value = MoveResult(status="moved", destination="HeadStart/Rejections")
        response = routing.route_classification(user_id, row)

    assert response.routing_status == "moved"
    assert response.routed_to == "HeadStart/Rejections"
    mock_move.assert_called_once()


def test_route_classification_skips_out_of_scope(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))
    row = _classification(user_id, label="out_of_scope")
    db_session.add(row)
    db_session.flush()

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        response = routing.route_classification(user_id, row)

    assert response.routing_status == "skipped"
    mock_move.assert_not_called()


def test_route_by_request_resolves_classification_id(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))
    row = _classification(user_id, label="general")
    db_session.add(row)
    db_session.flush()

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        mock_move.return_value = MoveResult(status="moved", destination="HeadStart/General")
        response = routing.route_by_request(user_id, InboxRouteRequest(classification_id=row.id))

    assert response.label == "general"
    assert response.routing_status == "moved"


def test_update_config_requires_credential(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    svc = InboxRoutingService(db_session)
    with pytest.raises(ValidationError):
        svc.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))


def test_route_classification_returns_early_when_already_moved(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))
    row = _classification(user_id)
    row.routing_status = "moved"
    row.routed_to = "HeadStart/Rejections"
    db_session.add(row)
    db_session.flush()

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        response = routing.route_classification(user_id, row)

    mock_move.assert_not_called()
    assert response.routing_status == "moved"


def test_route_classification_raises_without_context(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))
    row = _classification(user_id)
    db_session.add(row)
    db_session.flush()

    with (
        patch.object(routing.inbox, "resolve_context", return_value=None),
        pytest.raises(ValidationError),
    ):
        routing.route_classification(user_id, row)


def test_route_after_classify_routes_when_auto_route_enabled(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(
        user_id,
        InboxRoutingConfigUpdate(enabled=True, auto_route_on_classify=True),
    )
    row = _classification(user_id)
    db_session.add(row)
    db_session.flush()

    with patch.object(routing, "route_classification") as mock_route:
        returned = routing.route_after_classify(user_id, row)

    assert returned is row
    mock_route.assert_called_once_with(user_id, row)


def test_route_after_classify_noop_when_disabled(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=False))
    row = _classification(user_id)
    db_session.add(row)
    db_session.flush()

    with patch.object(routing, "route_classification") as mock_route:
        returned = routing.route_after_classify(user_id, row)

    assert returned is row
    mock_route.assert_not_called()


def test_route_by_request_requires_an_identifier(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    with pytest.raises(ValidationError):
        routing.route_by_request(user_id, InboxRouteRequest())


def test_route_by_request_unknown_classification_id(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    with pytest.raises(NotFoundError):
        routing.route_by_request(user_id, InboxRouteRequest(classification_id=999))


def test_route_by_request_resolves_message_uid(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    routing.update_config(user_id, InboxRoutingConfigUpdate(enabled=True))
    row = _classification(user_id, label="general", uid=77)
    db_session.add(row)
    db_session.flush()

    with patch("app.inbox.adapters.imap_smtp.ImapSmtpMailbox.move_message") as mock_move:
        mock_move.return_value = MoveResult(status="moved", destination="HeadStart/General")
        response = routing.route_by_request(user_id, InboxRouteRequest(message_uid=77))

    assert response.message_uid == 77
    assert response.routing_status == "moved"


def test_route_by_request_unknown_message_uid(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    _credential(db_session, user_id)
    routing = InboxRoutingService(db_session)
    with pytest.raises(NotFoundError):
        routing.route_by_request(user_id, InboxRouteRequest(message_uid=12345))


def test_provider_message_id_from_classification() -> None:
    assert (
        _provider_message_id_from_classification(
            InboxClassification(
                user_id=1,
                message_uid=1,
                label="general",
                confidence=1.0,
                reason="r",
                provider="heuristic",
                payload=None,
            )
        )
        is None
    )
    graph = InboxClassification(
        user_id=1,
        message_uid=1,
        label="general",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        payload={"graph_message_id": "G1"},
    )
    assert _provider_message_id_from_classification(graph) == "G1"
    jmap = InboxClassification(
        user_id=1,
        message_uid=1,
        label="general",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        payload={"jmap_email_id": "J1"},
    )
    assert _provider_message_id_from_classification(jmap) == "J1"
    none_match = InboxClassification(
        user_id=1,
        message_uid=1,
        label="general",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        payload={"unrelated": "x"},
    )
    assert _provider_message_id_from_classification(none_match) is None
