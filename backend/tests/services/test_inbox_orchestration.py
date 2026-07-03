"""Tests for beat-driven inbox orchestration."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import FetchResult, InboxMessage
from app.models.inbox_classification import InboxClassification
from app.models.user import User
from app.repositories.inbox_poll_state import InboxPollStateRepository
from app.schemas.mailbox import MailboxConfig, MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_orchestration import InboxOrchestrationService


def _user(session: Session, email: str = "orchestrate@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    return user.id


def _mailbox_config() -> MailboxConfig:
    return MailboxConfig(
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="imap-pass",
        smtp_host="smtp.example.com",
        smtp_password="smtp-pass",
        smtp_from="user@example.com",
    )


def test_process_due_disabled_when_inbox_agent_off(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    result = InboxOrchestrationService(db_session).process_due()
    assert result.users == 0
    assert result.fetched == 0


def test_process_due_classifies_fetched_messages(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )

    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=10,
                from_addr="hr@company.com",
                subject="Interview",
                body_text="Please schedule a phone screen using Calendly.",
            ),
            InboxMessage(
                uid=11,
                from_addr="noreply@company.com",
                subject="Rejection",
                body_text="Unfortunately we chose other candidates.",
            ),
        ],
        max_uid=11,
    )

    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result):
        result = service.process_due()

    assert result.users == 1
    assert result.fetched == 2
    assert result.classified == 2
    assert result.failed == 0
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user_id) == 11

    rows = db_session.query(InboxClassification).filter_by(user_id=user_id).all()
    assert len(rows) == 2
    assert {row.message_uid for row in rows} == {10, 11}


def test_process_due_skips_already_classified_and_advances_cursor(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    db_session.add(
        InboxClassification(
            user_id=user_id,
            message_uid=5,
            label="general",
            confidence=1.0,
            reason="seed",
            provider="heuristic",
            fallback=False,
            subject="Old",
            from_addr="hr@example.com",
            payload={},
        )
    )
    db_session.flush()
    InboxPollStateRepository(db_session).upsert_last_polled_uid(user_id, 5)

    fetch_result = FetchResult(
        messages=[
            InboxMessage(uid=6, subject="Update", body_text="Thanks for applying."),
        ],
        max_uid=6,
    )

    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result) as mock_fetch:
        result = service.process_due()

    mock_fetch.assert_called_once_with(user_id, since_uid=5, limit=settings.inbox_poll_batch_size)
    assert result.classified == 1
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user_id) == 6


def test_process_due_stops_on_classify_failure_without_advancing_past_failure(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )

    fetch_result = FetchResult(
        messages=[
            InboxMessage(uid=20, subject="One", body_text="First message."),
            InboxMessage(uid=21, subject="Two", body_text="Second message."),
        ],
        max_uid=21,
    )

    service = InboxOrchestrationService(db_session)
    classify_mock = MagicMock(side_effect=[None, RuntimeError("classifier down")])
    with (
        patch.object(service.inbox, "fetch_messages", return_value=fetch_result),
        patch.object(service.classifier, "classify", classify_mock),
    ):
        result = service.process_due()

    assert result.fetched == 2
    assert result.classified == 1
    assert result.failed == 1
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user_id) == 20


def test_process_due_bootstrap_since_uid_from_classifications(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id = _user(db_session)
    InboxService(db_session).upsert(
        user_id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=_mailbox_config()),
    )
    db_session.add(
        InboxClassification(
            user_id=user_id,
            message_uid=99,
            label="general",
            confidence=1.0,
            reason="seed",
            provider="heuristic",
            fallback=False,
            subject="Prior",
            from_addr="hr@example.com",
            payload={},
        )
    )
    db_session.flush()

    fetch_result = FetchResult(messages=[], max_uid=99)
    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result) as mock_fetch:
        service.process_due()

    mock_fetch.assert_called_once_with(user_id, since_uid=99, limit=settings.inbox_poll_batch_size)
