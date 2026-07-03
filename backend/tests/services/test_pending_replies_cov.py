"""Additional coverage tests for the inbox pending-reply delay queue."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import SendResult
from app.schemas.inbox_routing import InboxRoutingConfigUpdate
from app.services.inbox_routing import InboxRoutingService
from app.services.pending_replies import PendingReplyService
from app.services.reply_safe_send import SafeSendDecision
from tests.services.test_pending_replies import _seed_draft, _seed_mailbox
from tests.worker.test_pipeline import _make_search


class _FakeRow:
    """Stand-in for InboxPendingReply exercising _send_one's guard branches."""

    def __init__(self, user_id: int, draft: object) -> None:
        self.user_id = user_id
        self.draft = draft
        self.status = "pending"
        self.error: str | None = None
        self.sent_at = None
        self.payload: dict | None = None


class _FakeDraft:
    def __init__(self, classification: object) -> None:
        self.classification = classification
        self.status = "queued"


def test_auto_reply_enabled_false_without_credential(db_session: Session) -> None:
    search = _make_search(db_session)
    assert PendingReplyService(db_session).auto_reply_enabled(search.user_id) is False


def test_process_due_disabled_when_inbox_agent_off(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", False)
    result = PendingReplyService(db_session).process_due()
    assert result.checked == 0
    assert result.sent == 0


def test_enqueue_returns_existing_pending_row(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)
    first = service.enqueue_for_draft(user_id, draft)
    assert first is not None
    second = service.enqueue_for_draft(user_id, draft)
    assert second is not None
    assert second.id == first.id


def test_enqueue_cancels_and_requeues_when_prior_terminal(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)
    first = service.enqueue_for_draft(user_id, draft)
    assert first is not None
    first.status = "failed"
    first.error = "prior failure"
    db_session.flush()
    second = service.enqueue_for_draft(user_id, draft)
    assert second is not None
    assert second.id == first.id
    assert second.status == "pending"
    assert second.error is None


def test_enqueue_blocked_before_queue_records_and_returns_none(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)

    blocked = SafeSendDecision(allowed=False, outcome="blocked_topic", reason="blocked", payload={})
    with (
        patch.object(service.safe_send, "evaluate_before_queue", return_value=blocked),
        patch.object(service.safe_send, "record") as record_mock,
    ):
        result = service.enqueue_for_draft(user_id, draft)

    assert result is None
    record_mock.assert_called_once()


def test_send_one_skips_when_auto_reply_disabled_at_send(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    InboxRoutingService(db_session).update_config(
        user_id, InboxRoutingConfigUpdate(auto_reply_enabled=False)
    )
    result = service.process_due(now=now)

    assert result.skipped == 1
    assert row.status == "cancelled"
    assert draft.status == "draft"


def test_send_one_skips_when_disabled_and_draft_none(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=False)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = _FakeRow(user_id, draft=None)

    outcome = service._send_one(row, now=now)  # type: ignore[arg-type]

    assert outcome == "skipped"
    assert row.status == "cancelled"


def test_send_one_fails_when_draft_missing(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = _FakeRow(user_id, draft=None)

    outcome = service._send_one(row, now=now)  # type: ignore[arg-type]

    assert outcome == "failed"
    assert row.status == "failed"
    assert row.error == "draft missing"


def test_send_one_fails_when_classification_missing(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    draft = _FakeDraft(classification=None)
    row = _FakeRow(user_id, draft=draft)

    outcome = service._send_one(row, now=now)  # type: ignore[arg-type]

    assert outcome == "failed"
    assert row.status == "failed"
    assert row.error == "classification missing"
    assert draft.status == "failed"


def test_send_one_fails_on_send_exception(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    with patch.object(service.inbox, "send_message", side_effect=RuntimeError("smtp boom")):
        result = service.process_due(now=now)

    assert result.failed == 1
    assert row.status == "failed"
    assert "smtp boom" in row.error
    assert draft.status == "failed"


def test_send_one_fails_when_send_result_not_sent(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    with patch.object(
        service.inbox,
        "send_message",
        return_value=SendResult(status="failed", error="mailbox full"),
    ):
        result = service.process_due(now=now)

    assert result.failed == 1
    assert row.status == "failed"
    assert row.error == "mailbox full"
    assert draft.status == "failed"


def test_process_due_counts_blocked_outcome(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 0)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    blocked = SafeSendDecision(allowed=False, outcome="blocked_topic", reason="blocked", payload={})
    with patch.object(service.safe_send, "evaluate_before_send", return_value=blocked):
        result = service.process_due(now=now)

    assert result.blocked == 1
    assert row.status == "blocked"


def test_compute_send_after_applies_jitter(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_reply_min_delay_seconds", 60)
    monkeypatch.setattr(settings, "inbox_reply_delay_jitter_seconds", 30)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    with patch("app.services.pending_replies.random.randint", return_value=10):
        send_after = service.compute_send_after(now=now)
    assert send_after == now + timedelta(seconds=70)


def test_queue_snapshot_missing_returns_none(db_session: Session) -> None:
    search = _make_search(db_session)
    status, send_after = PendingReplyService(db_session).queue_snapshot(search.user_id, 999)
    assert status is None
    assert send_after is None
