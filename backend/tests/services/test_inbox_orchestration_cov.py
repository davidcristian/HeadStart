"""Additional coverage tests for beat-driven inbox orchestration."""

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import FetchResult, InboxMessage
from app.models.inbox_classification import InboxClassification
from app.repositories.inbox_poll_state import InboxPollStateRepository
from app.schemas.mailbox import MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_orchestration import InboxOrchestrationService
from tests.services.inbox_helpers import mailbox_config, make_user, seed_applied_job


def test_list_pollable_includes_env_credential_users(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    user = make_user(db_session, email="orchestrate-env@example.test")
    service = InboxOrchestrationService(db_session)
    from app.inbox.types import MailboxConfig

    env_config = MailboxConfig(
        imap_host="env-imap", imap_user="env@example.com", imap_password="p", smtp_host="env-smtp"
    )
    with (
        patch("app.services.inbox_orchestration.env_mailbox_config", return_value=env_config),
        patch.object(service.inbox, "resolve_context") as ctx_mock,
    ):
        from app.inbox.types import MailboxContext

        ctx_mock.return_value = MailboxContext(
            connector_type="imap_smtp", config=env_config, user_id=user.id
        )
        pollable = service._list_pollable_user_ids()

    assert user.id in pollable


def test_list_pollable_skips_user_already_enabled(db_session: Session, monkeypatch) -> None:
    # A user with an enabled credential is already collected; the env-fallback loop must
    # skip them via `continue` rather than re-adding.
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    user = make_user(db_session, email="orchestrate-dup@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    service = InboxOrchestrationService(db_session)
    from app.inbox.types import MailboxConfig

    env_config = MailboxConfig(
        imap_host="env-imap", imap_user="env@example.com", imap_password="p", smtp_host="env-smtp"
    )
    with patch("app.services.inbox_orchestration.env_mailbox_config", return_value=env_config):
        pollable = service._list_pollable_user_ids()

    assert pollable == [user.id]


def test_process_due_stops_on_first_message_failure_keeps_cursor(
    db_session: Session, monkeypatch
) -> None:
    # First classifiable message fails, so last_success_uid never advances past since_uid
    # (None) and the poll cursor is left unset.
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-firstfail@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    seed_applied_job(db_session, user)
    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=80,
                from_addr="hr@careers.company.com",
                subject="One",
                body_text="First message.",
            ),
        ],
        max_uid=80,
    )
    service = InboxOrchestrationService(db_session)
    with (
        patch.object(service.inbox, "fetch_messages", return_value=fetch_result),
        patch.object(service.classifier, "classify", side_effect=RuntimeError("down")),
    ):
        result = service.process_due()

    assert result.failed == 1
    assert result.classified == 0
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) is None


def test_list_pollable_skips_env_user_without_context(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_use_env_credentials", True)
    make_user(db_session, email="orchestrate-noctx@example.test")
    service = InboxOrchestrationService(db_session)
    from app.inbox.types import MailboxConfig

    env_config = MailboxConfig(
        imap_host="env-imap", imap_user="env@example.com", imap_password="p", smtp_host="env-smtp"
    )
    with (
        patch("app.services.inbox_orchestration.env_mailbox_config", return_value=env_config),
        patch.object(service.inbox, "resolve_context", return_value=None),
    ):
        pollable = service._list_pollable_user_ids()

    assert pollable == []


def test_process_user_skips_when_no_context(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-skipctx@example.test")
    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "resolve_context", return_value=None):
        result = service._process_user(user.id)
    assert result.skipped == 1


def test_process_user_records_fetch_failure(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-fetchfail@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", side_effect=RuntimeError("imap down")):
        result = service._process_user(user.id)
    assert result.failed == 1
    assert result.fetched == 0


def test_process_due_advances_cursor_on_empty_with_new_max_uid(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-empty@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    fetch_result = FetchResult(messages=[], max_uid=50)
    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result):
        result = service.process_due()
    assert result.fetched == 0
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) == 50


def test_process_due_ignored_only_still_advances_cursor(db_session: Session, monkeypatch) -> None:
    # last_success_uid advances via ignored mail; cursor updates because it differs from since_uid.
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-ignoreonly@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    fetch_result = FetchResult(
        messages=[
            InboxMessage(
                uid=60,
                from_addr="news@shopping.example",
                subject="Weekly deals",
                body_text="50% off.",
            ),
        ],
        max_uid=60,
    )
    service = InboxOrchestrationService(db_session)
    with patch.object(service.inbox, "fetch_messages", return_value=fetch_result):
        result = service.process_due()
    assert result.ignored == 1
    assert result.classified == 0
    assert InboxPollStateRepository(db_session).get_last_polled_uid(user.id) == 60


def test_maybe_auto_draft_reply_drafts_when_enabled(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-autodraft@example.test")
    InboxService(db_session).upsert(
        user.id,
        MailboxCredentialUpsert(connector_type="imap_smtp", config=mailbox_config()),
    )
    db_session.add(
        InboxClassification(
            user_id=user.id,
            message_uid=70,
            label="follow_up",
            confidence=1.0,
            reason="r",
            provider="heuristic",
            subject="Q",
            from_addr="hr@acme.com",
            payload={},
        )
    )
    db_session.flush()
    service = InboxOrchestrationService(db_session)
    with (
        patch.object(service.pending_replies, "auto_reply_enabled", return_value=True),
        patch.object(service.reply_drafts, "draft") as draft_mock,
    ):
        service._maybe_auto_draft_reply(user.id, 70)
    draft_mock.assert_called_once()


def test_maybe_auto_draft_reply_noop_when_disabled(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-nodraft@example.test")
    service = InboxOrchestrationService(db_session)
    with (
        patch.object(service.pending_replies, "auto_reply_enabled", return_value=False),
        patch.object(service.reply_drafts, "draft") as draft_mock,
    ):
        service._maybe_auto_draft_reply(user.id, 70)
    draft_mock.assert_not_called()


def test_maybe_auto_draft_reply_noop_when_not_draftable(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-notdraftable@example.test")
    db_session.add(
        InboxClassification(
            user_id=user.id,
            message_uid=71,
            label="rejection",
            confidence=1.0,
            reason="r",
            provider="heuristic",
            subject="No",
            from_addr="hr@acme.com",
            payload={},
        )
    )
    db_session.flush()
    service = InboxOrchestrationService(db_session)
    with (
        patch.object(service.pending_replies, "auto_reply_enabled", return_value=True),
        patch.object(service.reply_drafts, "draft") as draft_mock,
    ):
        service._maybe_auto_draft_reply(user.id, 71)
        service._maybe_auto_draft_reply(user.id, 9999)
    draft_mock.assert_not_called()


def test_maybe_auto_draft_reply_swallows_exceptions(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user = make_user(db_session, email="orchestrate-draftfail@example.test")
    db_session.add(
        InboxClassification(
            user_id=user.id,
            message_uid=72,
            label="follow_up",
            confidence=1.0,
            reason="r",
            provider="heuristic",
            subject="Q",
            from_addr="hr@acme.com",
            payload={},
        )
    )
    db_session.flush()
    service = InboxOrchestrationService(db_session)
    with (
        patch.object(service.pending_replies, "auto_reply_enabled", return_value=True),
        patch.object(service.reply_drafts, "draft", side_effect=RuntimeError("draft boom")),
    ):
        # Must not raise.
        service._maybe_auto_draft_reply(user.id, 72)
