"""Service tests for inbox pending reply delay queue."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import OutboundMessage, SendResult
from app.models.application_log import ApplicationLog
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft
from app.models.seen_job import SeenJob
from app.schemas.inbox_routing import InboxRoutingConfigUpdate
from app.schemas.mailbox import MailboxCredentialUpsert
from app.services.inbox import InboxService
from app.services.inbox_routing import InboxRoutingService
from app.services.pending_replies import PendingReplyService
from tests.services.test_inbox import _sample_config
from tests.worker.test_pipeline import _make_search


def _seed_mailbox(session: Session, user_id: int, *, auto_reply: bool = True) -> None:
    InboxService(session).upsert(user_id, MailboxCredentialUpsert(config=_sample_config()))
    InboxRoutingService(session).update_config(
        user_id,
        InboxRoutingConfigUpdate(auto_reply_enabled=auto_reply),
    )


def _seed_draft(session: Session, user_id: int, *, search=None) -> InboxReplyDraft:
    seen_job_id = None
    if search is not None:
        job = SeenJob(
            search_id=search.id,
            external_id="ext-42",
            hash="a" * 64,
            title="Engineer",
            company="ACME",
            url="https://jobs.acme.com/role",
        )
        session.add(job)
        session.flush()
        log = ApplicationLog(
            seen_job_id=job.id,
            status="submitted",
            dry_run=False,
            payload={"employer_domain": "acme.com"},
        )
        session.add(log)
        session.flush()
        job.application_logs = [log]
        seen_job_id = job.id

    classification = InboxClassification(
        user_id=user_id,
        seen_job_id=seen_job_id,
        message_uid=42,
        message_id="<msg-42@acme.com>",
        label="follow_up",
        confidence=0.9,
        reason="test",
        provider="heuristic",
        subject="Quick question",
        from_addr="hr@acme.com",
        payload={"references": "<thread-root@acme.com>"},
        created_at=datetime(2026, 6, 30, 10, 0, tzinfo=UTC),
    )
    session.add(classification)
    session.flush()
    draft = InboxReplyDraft(
        user_id=user_id,
        inbox_classification_id=classification.id,
        message_uid=42,
        subject="Re: Quick question",
        body_text="Thanks for reaching out.",
        provider="heuristic",
        status="draft",
    )
    session.add(draft)
    session.flush()
    draft.classification = classification
    return draft


def test_compute_send_after_enforces_minimum_delay(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_reply_min_delay_seconds", 30)
    monkeypatch.setattr(settings, "inbox_reply_delay_jitter_seconds", 0)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    send_after = service.compute_send_after(now=now, anchor=now)
    assert send_after == now + timedelta(seconds=60)


def test_enqueue_for_draft_when_auto_reply_enabled(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_min_delay_seconds", 1800)
    monkeypatch.setattr(settings, "inbox_reply_delay_jitter_seconds", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    with patch.object(service, "compute_send_after", return_value=now + timedelta(minutes=30)):
        row = service.enqueue_for_draft(user_id, draft, anchor=now)

    assert row is not None
    assert row.status == "pending"
    assert draft.status == "queued"
    queue_status, send_after = service.queue_snapshot(user_id, draft.id)
    assert queue_status == "pending"
    assert send_after == now + timedelta(minutes=30)


def test_enqueue_skipped_when_auto_reply_disabled(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=False)
    draft = _seed_draft(db_session, user_id, search=search)
    service = PendingReplyService(db_session)
    assert service.enqueue_for_draft(user_id, draft) is None
    assert draft.status == "draft"


def test_process_due_sends_after_delay(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    with patch.object(
        service.inbox,
        "send_message",
        return_value=SendResult(status="sent"),
    ) as send_mock:
        result = service.process_due(now=now)

    assert result.sent == 1
    assert row.status == "sent"
    assert draft.status == "sent"
    send_mock.assert_called_once()
    outbound = send_mock.call_args.args[1]
    assert isinstance(outbound, OutboundMessage)
    assert outbound.to == ["hr@acme.com"]
    assert outbound.in_reply_to == "<msg-42@acme.com>"


def test_process_due_skips_before_send_after(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now)
    assert row is not None
    row.send_after = now + timedelta(minutes=30)

    with patch.object(service.inbox, "send_message") as send_mock:
        result = service.process_due(now=now)

    assert result.checked == 0
    send_mock.assert_not_called()
    assert row.status == "pending"
