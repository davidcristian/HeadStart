"""Direct unit tests for inbox-related repositories."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.inbox_classification import InboxClassification
from app.models.inbox_pending_reply import InboxPendingReply
from app.models.inbox_reply_draft import InboxReplyDraft
from app.models.notification_target import NotificationTarget
from app.models.search import Search
from app.models.seen_job import SeenJob
from app.models.source import Source
from app.models.user import User
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_pending_replies import InboxPendingReplyRepository
from app.repositories.inbox_reply_drafts import InboxReplyDraftRepository


def _seen_job(session: Session, user_id: int) -> SeenJob:
    source = Source(
        user_id=user_id,
        name="Inbox source",
        adapter_key="greenhouse",
        base_url="https://inbox.example.test",
        default_config={},
        enabled=True,
    )
    target = NotificationTarget(
        user_id=user_id,
        name="Inbox target",
        type="email",
        config={"to": "inbox@example.test"},
    )
    session.add_all([source, target])
    session.flush()
    search = Search(
        user_id=user_id,
        source_id=source.id,
        target_id=target.id,
        name="Inbox search",
        query_url="https://inbox.example.test/jobs",
        filters={},
        config={},
        interval_seconds=300,
        notification_mode="immediate",
        digest_interval_seconds=3600,
        enabled=True,
        next_run_at=utcnow(),
    )
    session.add(search)
    session.flush()
    job = SeenJob(
        search_id=search.id,
        external_id=f"inbox-{search.id}",
        hash=f"inbox-{search.id}",
        title="Role",
        company="Co",
        url="https://inbox.example.test/jobs/1",
        status="new",
    )
    session.add(job)
    session.flush()
    return job


def _user(session: Session, email: str = "inbox@example.test") -> User:
    user = User(email=email, password_hash="x", is_active=True)
    session.add(user)
    session.flush()
    return user


def _classification(
    session: Session,
    user_id: int,
    *,
    message_uid: int,
    label: str = "follow_up",
    seen_job_id: int | None = None,
) -> InboxClassification:
    row = InboxClassification(
        user_id=user_id,
        seen_job_id=seen_job_id,
        message_uid=message_uid,
        label=label,
        confidence=0.9,
        provider="heuristic",
    )
    session.add(row)
    session.flush()
    return row


def _draft(
    session: Session,
    user_id: int,
    classification_id: int,
    *,
    seen_job_id: int | None = None,
) -> InboxReplyDraft:
    row = InboxReplyDraft(
        user_id=user_id,
        inbox_classification_id=classification_id,
        seen_job_id=seen_job_id,
        message_uid=1,
        body_text="hi",
        provider="heuristic",
    )
    session.add(row)
    session.flush()
    return row


# ---- InboxReplyDraftRepository ----


def test_reply_draft_list_filters_by_seen_job(db_session: Session) -> None:
    user = _user(db_session)
    job_a = _seen_job(db_session, user.id)
    job_b = _seen_job(db_session, user.id)
    cls_a = _classification(db_session, user.id, message_uid=1)
    cls_b = _classification(db_session, user.id, message_uid=2)
    _draft(db_session, user.id, cls_a.id, seen_job_id=job_a.id)
    _draft(db_session, user.id, cls_b.id, seen_job_id=job_b.id)
    repo = InboxReplyDraftRepository(db_session)

    matches = repo.list_for_user(user.id, seen_job_id=job_a.id)
    assert [d.seen_job_id for d in matches] == [job_a.id]


def test_reply_draft_latest_by_seen_job_ids_dedups(db_session: Session) -> None:
    user = _user(db_session)
    job = _seen_job(db_session, user.id)
    cls_a = _classification(db_session, user.id, message_uid=1)
    cls_b = _classification(db_session, user.id, message_uid=2)
    older = _draft(db_session, user.id, cls_a.id, seen_job_id=job.id)
    older.created_at = utcnow() - timedelta(hours=1)
    newer = _draft(db_session, user.id, cls_b.id, seen_job_id=job.id)
    newer.created_at = utcnow()
    db_session.flush()
    repo = InboxReplyDraftRepository(db_session)

    latest = repo.latest_by_seen_job_ids(user.id, [job.id])
    assert latest[job.id].id == newer.id


def test_reply_draft_latest_by_seen_job_ids_empty(db_session: Session) -> None:
    assert InboxReplyDraftRepository(db_session).latest_by_seen_job_ids(1, []) == {}


def test_reply_draft_delete_and_count(db_session: Session) -> None:
    user = _user(db_session)
    cls = _classification(db_session, user.id, message_uid=1)
    draft = _draft(db_session, user.id, cls.id)
    repo = InboxReplyDraftRepository(db_session)
    assert repo.count_for_user(user.id) == 1

    repo.delete(draft)
    assert repo.count_for_user(user.id) == 0


# ---- InboxPendingReplyRepository ----


def _pending(
    session: Session, user_id: int, draft_id: int, *, status: str = "pending"
) -> InboxPendingReply:
    row = InboxPendingReply(
        user_id=user_id,
        inbox_reply_draft_id=draft_id,
        send_after=utcnow(),
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def test_pending_reply_cancel_for_missing_draft_is_noop(db_session: Session) -> None:
    InboxPendingReplyRepository(db_session).cancel_for_draft(1, 999)  # no row exists


def test_pending_reply_cancel_skips_already_finalized(db_session: Session) -> None:
    user = _user(db_session)
    cls = _classification(db_session, user.id, message_uid=1)
    draft = _draft(db_session, user.id, cls.id)
    pending = _pending(db_session, user.id, draft.id, status="sent")
    repo = InboxPendingReplyRepository(db_session)

    repo.cancel_for_draft(user.id, draft.id)
    db_session.refresh(pending)
    assert pending.status == "sent"  # untouched


def test_pending_reply_cancel_marks_pending_cancelled(db_session: Session) -> None:
    user = _user(db_session)
    cls = _classification(db_session, user.id, message_uid=1)
    draft = _draft(db_session, user.id, cls.id)
    pending = _pending(db_session, user.id, draft.id, status="pending")
    pending.error = "boom"
    db_session.flush()
    repo = InboxPendingReplyRepository(db_session)

    repo.cancel_for_draft(user.id, draft.id)
    db_session.refresh(pending)
    assert pending.status == "cancelled"
    assert pending.error is None


# ---- InboxClassificationRepository ----


def test_classification_latest_draftable_dedups(db_session: Session) -> None:
    user = _user(db_session)
    job = _seen_job(db_session, user.id)
    older = _classification(db_session, user.id, message_uid=1, seen_job_id=job.id)
    older.created_at = utcnow() - timedelta(hours=1)
    newer = _classification(db_session, user.id, message_uid=2, seen_job_id=job.id)
    newer.created_at = utcnow()
    db_session.flush()
    repo = InboxClassificationRepository(db_session)

    latest = repo.latest_draftable_by_seen_job_ids(user.id, [job.id])
    assert latest[job.id].id == newer.id
