"""Service tests for reply safe-send guardrails."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.config import settings
from app.inbox.types import SendResult
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_send_log import InboxReplySendLog
from app.services.pending_replies import PendingReplyService
from app.services.reply_safe_send import ReplySafeSendService
from tests.services.test_pending_replies import _seed_draft, _seed_mailbox
from tests.worker.test_pipeline import _make_search


def test_enqueue_blocks_sensitive_topic_and_writes_audit_log(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    draft.body_text = "Happy to discuss the discrimination complaint with HR."
    service = PendingReplyService(db_session)

    row = service.enqueue_for_draft(user_id, draft)

    assert row is None
    assert draft.status == "draft"
    logs = ReplySafeSendService(db_session).list_for_user(user_id)
    assert len(logs) == 1
    assert logs[0].outcome == "blocked_topic"
    assert "discrimination" in logs[0].reason


def test_process_due_blocks_hourly_rate_limit(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 1)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    db_session.add(
        InboxReplySendLog(
            user_id=user_id,
            inbox_reply_draft_id=draft.id,
            outcome="sent",
            reason="",
            subject="Earlier reply",
            body_excerpt="sent earlier",
            created_at=now - timedelta(minutes=10),
        )
    )
    db_session.flush()

    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    with patch.object(
        service.inbox,
        "send_message",
        return_value=SendResult(status="sent"),
    ) as send_mock:
        result = service.process_due(now=now)

    assert result.blocked == 1
    assert result.sent == 0
    send_mock.assert_not_called()
    assert row.status == "blocked"
    assert draft.status == "draft"
    logs = ReplySafeSendService(db_session).list_for_user(user_id, limit=10)
    assert any(log.outcome == "blocked_rate_limit_hour" for log in logs)


def test_process_due_records_sent_audit_log(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 0)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = PendingReplyService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    row = service.enqueue_for_draft(user_id, draft, anchor=now - timedelta(hours=1))
    assert row is not None
    row.send_after = now - timedelta(minutes=1)

    with patch.object(service.inbox, "send_message", return_value=SendResult(status="sent")):
        result = service.process_due(now=now)

    assert result.sent == 1
    logs = ReplySafeSendService(db_session).list_for_user(user_id, limit=10)
    assert any(log.outcome == "sent" for log in logs)


def test_evaluate_before_send_blocks_on_topic(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    draft.body_text = "Let's discuss the discrimination complaint you raised."
    db_session.flush()
    service = ReplySafeSendService(db_session)

    decision = service.evaluate_before_send(user_id, draft, draft.classification)

    assert decision.allowed is False
    assert decision.outcome == "blocked_topic"
    assert "matched_topics" in decision.payload


def test_evaluate_before_send_blocks_on_daily_limit(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 0)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 1)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = ReplySafeSendService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    db_session.add(
        InboxReplySendLog(
            user_id=user_id,
            inbox_reply_draft_id=draft.id,
            outcome="sent",
            reason="",
            subject="Earlier",
            body_excerpt="earlier",
            created_at=now - timedelta(hours=3),
        )
    )
    db_session.flush()

    decision = service.evaluate_before_send(user_id, draft, draft.classification, now=now)

    assert decision.allowed is False
    assert decision.outcome == "blocked_rate_limit_day"
    assert decision.payload["limit"] == 1


def test_evaluate_before_send_allows_under_both_caps(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 5)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 10)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = ReplySafeSendService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    decision = service.evaluate_before_send(user_id, draft, draft.classification, now=now)

    assert decision.allowed is True
    assert decision.outcome == "sent"


def test_reserve_before_send_second_call_hits_hourly_cap(db_session: Session, monkeypatch) -> None:
    """A reserved slot counts toward the cap so overlapping sends cannot both pass."""
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 1)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft_a = _seed_draft(db_session, user_id, search=search)
    draft_b = _seed_draft(db_session, user_id, search=search, message_uid=2)
    service = ReplySafeSendService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    first, reserved = service.reserve_before_send(user_id, draft_a, draft_a.classification, now=now)
    second, blocked = service.reserve_before_send(user_id, draft_b, draft_b.classification, now=now)

    assert first.allowed is True
    assert reserved.outcome == "reserved"
    assert second.allowed is False
    assert second.outcome == "blocked_rate_limit_hour"
    assert blocked.outcome == "blocked_rate_limit_hour"


def test_release_reservation_frees_rate_slot(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 1)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft_a = _seed_draft(db_session, user_id, search=search)
    draft_b = _seed_draft(db_session, user_id, search=search, message_uid=2)
    service = ReplySafeSendService(db_session)
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    _, reserved = service.reserve_before_send(user_id, draft_a, draft_a.classification, now=now)
    service.release_reservation(reserved)
    retry, again = service.reserve_before_send(user_id, draft_b, draft_b.classification, now=now)

    assert retry.allowed is True
    assert again.outcome == "reserved"


def test_finalize_reservation_marks_sent(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 0)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    service = ReplySafeSendService(db_session)

    _, reserved = service.reserve_before_send(user_id, draft, draft.classification)
    service.finalize_reservation(reserved)

    assert reserved.outcome == "sent"


def test_process_due_releases_reservation_on_send_failure(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    monkeypatch.setattr(settings, "inbox_reply_max_per_hour", 1)
    monkeypatch.setattr(settings, "inbox_reply_max_per_day", 0)
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
        return_value=SendResult(status="failed", error="smtp down"),
    ):
        result = service.process_due(now=now)

    assert result.failed == 1
    logs = ReplySafeSendService(db_session).list_for_user(user_id, limit=20)
    assert not any(log.outcome in {"sent", "reserved"} for log in logs)

    # Cap slot was released; a later due send can still reserve.
    draft2 = _seed_draft(db_session, user_id, search=search, message_uid=3)
    row2 = service.enqueue_for_draft(user_id, draft2, anchor=now - timedelta(hours=1))
    assert row2 is not None
    row2.send_after = now - timedelta(minutes=1)
    with patch.object(service.inbox, "send_message", return_value=SendResult(status="sent")):
        retry = service.process_due(now=now)
    assert retry.sent == 1


def test_inbound_body_empty_without_classification_or_payload(db_session: Session) -> None:
    service = ReplySafeSendService(db_session)
    assert service._inbound_body(None) == ""
    row = InboxClassification(
        user_id=1,
        message_uid=1,
        label="general",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        payload=None,
    )
    assert service._inbound_body(row) == ""
    non_str = InboxClassification(
        user_id=1,
        message_uid=1,
        label="general",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        payload={"body_excerpt": 123},
    )
    assert service._inbound_body(non_str) == ""


def test_body_excerpt_truncates_long_body(db_session: Session) -> None:
    service = ReplySafeSendService(db_session)
    long_text = "a" * 800
    excerpt = service._body_excerpt(long_text)
    assert len(excerpt) == 500
    assert excerpt.endswith("…")


def test_body_excerpt_short_body_unchanged(db_session: Session) -> None:
    service = ReplySafeSendService(db_session)
    assert service._body_excerpt("  short  ") == "short"


def test_inbound_body_unescapes_html_entities_for_topic_scan(db_session: Session) -> None:
    """HTML-encoded sensitive terms must still hit the topic blocklist."""
    service = ReplySafeSendService(db_session)
    # &#108;awsuit → lawsuit after html.unescape
    row = InboxClassification(
        user_id=1,
        message_uid=1,
        label="general",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        payload={"body_excerpt": "Please review this &#108;awsuit filing carefully."},
    )
    assert "lawsuit" in service._inbound_body(row).lower()


def test_evaluate_before_send_blocks_html_encoded_inbound_topic(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    assert draft.classification is not None
    draft.classification.payload = {
        "body_excerpt": "We received a <b>&#108;awsuit</b> notice yesterday."
    }
    db_session.flush()
    service = ReplySafeSendService(db_session)

    decision = service.evaluate_before_send(user_id, draft, draft.classification)

    assert decision.allowed is False
    assert decision.outcome == "blocked_topic"
    assert "lawsuit" in decision.payload["matched_topics"]


def test_evaluate_before_send_blocks_sensitive_topic_past_legacy_500_char_cut(
    db_session: Session, monkeypatch
) -> None:
    """Topic terms beyond the old raw 500-char excerpt must still block."""
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    user_id = search.user_id
    _seed_mailbox(db_session, user_id, auto_reply=True)
    draft = _seed_draft(db_session, user_id, search=search)
    assert draft.classification is not None
    # Simulate a post-fix classification payload that keeps text past 500 chars.
    draft.classification.payload = {
        "body_excerpt": ("x" * 520) + " Please discuss the harassment complaint."
    }
    db_session.flush()
    service = ReplySafeSendService(db_session)

    decision = service.evaluate_before_send(user_id, draft, draft.classification)

    assert decision.allowed is False
    assert decision.outcome == "blocked_topic"
    assert "harassment" in decision.payload["matched_topics"]
