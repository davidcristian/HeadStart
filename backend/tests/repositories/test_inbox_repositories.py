"""Direct unit tests for inbox-related repositories."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.inbox_classification import InboxClassification
from app.models.inbox_pending_reply import InboxPendingReply
from app.models.inbox_reply_draft import InboxReplyDraft
from app.models.user import User
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_pending_replies import InboxPendingReplyRepository
from app.repositories.inbox_reply_drafts import InboxReplyDraftRepository


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
    cls_a = _classification(db_session, user.id, message_uid=1)
    cls_b = _classification(db_session, user.id, message_uid=2)
    _draft(db_session, user.id, cls_a.id, seen_job_id=7)
    _draft(db_session, user.id, cls_b.id, seen_job_id=8)
    repo = InboxReplyDraftRepository(db_session)

    matches = repo.list_for_user(user.id, seen_job_id=7)
    assert [d.seen_job_id for d in matches] == [7]


def test_reply_draft_latest_by_seen_job_ids_dedups(db_session: Session) -> None:
    user = _user(db_session)
    cls_a = _classification(db_session, user.id, message_uid=1)
    cls_b = _classification(db_session, user.id, message_uid=2)
    older = _draft(db_session, user.id, cls_a.id, seen_job_id=5)
    older.created_at = utcnow() - timedelta(hours=1)
    newer = _draft(db_session, user.id, cls_b.id, seen_job_id=5)
    newer.created_at = utcnow()
    db_session.flush()
    repo = InboxReplyDraftRepository(db_session)

    latest = repo.latest_by_seen_job_ids(user.id, [5])
    assert latest[5].id == newer.id


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
    older = _classification(db_session, user.id, message_uid=1, seen_job_id=3)
    older.created_at = utcnow() - timedelta(hours=1)
    newer = _classification(db_session, user.id, message_uid=2, seen_job_id=3)
    newer.created_at = utcnow()
    db_session.flush()
    repo = InboxClassificationRepository(db_session)

    latest = repo.latest_draftable_by_seen_job_ids(user.id, [3])
    assert latest[3].id == newer.id
