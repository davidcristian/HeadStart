"""Tests for beat-driven inbox orchestration."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.email_classifiers.labels import GHOST_SUBJECT_PREFIX
from app.inbox.types import FetchResult, InboxMessage
from app.models.inbox_classification import InboxClassification
from app.repositories.inbox_poll_state import InboxPollStateRepository
from app.schemas.mailbox import MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_orchestration import InboxOrchestrationService
from tests.services.inbox_helpers import mailbox_config, make_user, seed_applied_job


def test_process_due_disabled_when_inbox_agent_off(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    result = InboxOrchestrationService(db_session).process_due()
    assert result.users == 0
    assert result.fetched == 0


def test_process_due_classifies_fetched_messages(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session)
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    seed_applied_job(db_session, user, employer_domain="company.com")

    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=10,
                from_addr="hr@careers.company.com",
                subject="Interview",
                body_text="Please schedule a phone screen using Calendly.",
            ),
            InboxMessage(
                uid=11,
                from_addr="noreply@careers.company.com",
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
    assert result.ignored == 0
    assert result.failed == 0
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) == 11

    rows = db_session.query(InboxClassification).filter_by(user_id=user.id).all()
    assert len(rows) == 2
    assert {row.message_uid for row in rows} == {10, 11}


def test_process_due_ignores_unrelated_mail_and_advances_cursor(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-ignore@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    seed_applied_job(db_session, user)

    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=30,
                from_addr="news@shopping.example",
                subject="Weekly deals",
                body_text="50% off.",
            ),
            InboxMessage(
                uid=31,
                from_addr="hr@careers.company.com",
                subject="Interview",
                body_text="Please schedule a phone screen using Calendly.",
            ),
        ],
        max_uid=31,
    )

    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result):
        result = service.process_due()

    assert result.fetched == 2
    assert result.ignored == 1
    assert result.classified == 1
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) == 31
    rows = db_session.query(InboxClassification).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].message_uid == 31


def test_process_due_classifies_self_ghost_archive_without_applications(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-ghost@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )

    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=40,
                from_addr="user@example.com",
                to_addrs=["user@example.com"],
                subject=f"{GHOST_SUBJECT_PREFIX} No reply: ACME — Engineer",
                body_text="Ghost summary.",
            ),
        ],
        max_uid=40,
    )

    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result):
        result = service.process_due()

    assert result.classified == 1
    assert result.ignored == 0
    rows = db_session.query(InboxClassification).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].label == "self_ghost_archive"


def test_process_due_skips_already_classified_and_advances_cursor(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-skip@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    seed_applied_job(db_session, user)
    db_session.add(
        InboxClassification(
            user_id=user.id,
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
    InboxPollStateRepository(db_session).upsert_last_polled_uid(user.id, 5)

    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=6,
                from_addr="hr@careers.company.com",
                subject="Update",
                body_text="Thanks for applying.",
            ),
        ],
        max_uid=6,
    )

    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result) as mock_fetch:
        result = service.process_due()

    mock_fetch.assert_called_once_with(user.id, since_uid=5, limit=settings.inbox_poll_batch_size)
    assert result.classified == 1
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) == 6


def test_process_due_stops_on_classify_failure_without_advancing_past_failure(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-fail@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    seed_applied_job(db_session, user)

    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=20,
                from_addr="hr@careers.company.com",
                subject="One",
                body_text="First message.",
            ),
            InboxMessage(
                uid=21,
                from_addr="hr@careers.company.com",
                subject="Two",
                body_text="Second message.",
            ),
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
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) == 20


def test_process_due_bootstrap_since_uid_from_classifications(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-bootstrap@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    db_session.add(
        InboxClassification(
            user_id=user.id,
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

    mock_fetch.assert_called_once_with(user.id, since_uid=99, limit=settings.inbox_poll_batch_size)
