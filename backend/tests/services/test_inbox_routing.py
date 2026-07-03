"""Service tests for inbox folder routing."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import MoveResult
from app.models.inbox_classification import InboxClassification
from app.models.user import User
from app.schemas.inbox_routing import InboxRouteRequest, InboxRoutingConfigUpdate
from app.schemas.mailbox import MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_routing import InboxRoutingService
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
