"""Additional coverage tests for inbox reply drafting internals."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft
from app.reply_drafters.types import ReplyDraftContext, ReplyDraftResult
from app.schemas.inbox_reply_draft import ReplyDraftRequest
from app.schemas.profile import ProfileData
from app.services.profiles import ProfileService
from app.services.reply_drafts import ReplyDraftService, _default_subject
from tests.services.test_reply_drafts import (
    StubDrafter,
    _classify_follow_up,
    _follow_up_classification,
    _seed_applied_job,
)
from tests.worker.test_pipeline import _make_search


def test_draft_disabled_raises(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    service = ReplyDraftService(db_session, settings=SimpleNamespace(reply_drafts_enabled=False))
    with pytest.raises(ValidationError):
        service.draft(user_id, ReplyDraftRequest(classification_id=1))


def test_draft_unknown_user_raises(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    service = ReplyDraftService(db_session)
    with pytest.raises(NotFoundError):
        service.draft(999, ReplyDraftRequest(classification_id=1))


def test_draft_requires_profile(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    classification = _classify_follow_up(db_session, user_id)
    service = ReplyDraftService(db_session)
    with (
        patch.object(service, "_resolve_provider", return_value="heuristic"),
        pytest.raises(ValidationError),
    ):
        service.draft(user_id, ReplyDraftRequest(classification_id=classification.id))


def test_draft_falls_back_when_llm_fails(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    ProfileService(db_session).save(user_id, ProfileData(full_name="Alex Example"))
    classification = _follow_up_classification(db_session, user_id, body_excerpt="Hi there.")

    def factory(key: str, runtime: object) -> object:
        if key == "heuristic":
            return StubDrafter()
        raise RuntimeError("llm down")

    service = ReplyDraftService(db_session, drafter_factory=factory)
    with patch.object(service, "_resolve_provider", return_value="openai"):
        result = service.draft(user_id, ReplyDraftRequest(classification_id=classification.id))

    assert result.provider == "heuristic"
    assert result.fallback is True


def test_draft_regenerate_replaces_existing(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    ProfileService(db_session).save(user_id, ProfileData(full_name="Alex Example"))
    classification = _classify_follow_up(db_session, user_id)
    service = ReplyDraftService(db_session)
    with patch.object(service, "_resolve_provider", return_value="heuristic"):
        first = service.draft(user_id, ReplyDraftRequest(classification_id=classification.id))
        with patch.object(service.drafts, "delete", wraps=service.drafts.delete) as del_mock:
            service.draft(
                user_id,
                ReplyDraftRequest(classification_id=classification.id, regenerate=True),
            )
    # Regeneration must delete the prior draft row before inserting the fresh one.
    del_mock.assert_called_once()
    assert first.id is not None


def test_draft_regenerate_without_existing_draft(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    ProfileService(db_session).save(user_id, ProfileData(full_name="Alex Example"))
    classification = _classify_follow_up(db_session, user_id)
    service = ReplyDraftService(db_session)
    with patch.object(service, "_resolve_provider", return_value="heuristic"):
        result = service.draft(
            user_id,
            ReplyDraftRequest(classification_id=classification.id, regenerate=True),
        )
    assert result.status == "draft"


def test_resolve_classification_by_id_not_found(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    service = ReplyDraftService(db_session)
    with pytest.raises(NotFoundError):
        service._resolve_classification(search.user_id, ReplyDraftRequest(classification_id=404))


def test_resolve_classification_by_uid(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    row = _follow_up_classification(db_session, user_id, body_excerpt="x")
    service = ReplyDraftService(db_session)
    found = service._resolve_classification(user_id, ReplyDraftRequest(message_uid=row.message_uid))
    assert found.id == row.id


def test_resolve_classification_by_uid_not_found(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    search = _make_search(db_session)
    service = ReplyDraftService(db_session)
    with pytest.raises(NotFoundError):
        service._resolve_classification(search.user_id, ReplyDraftRequest(message_uid=8888))


def test_build_context_linked_application_from_payload(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbox_agent_enabled", True)
    user_id, _job = _seed_applied_job(db_session)
    ProfileService(db_session).save(user_id, ProfileData(full_name="Alex Example"))
    row = InboxClassification(
        user_id=user_id,
        message_uid=13,
        label="follow_up",
        confidence=0.9,
        reason="r",
        provider="heuristic",
        subject="Quick question",
        from_addr="hr@acme.com",
        payload={
            "body_excerpt": 12345,  # non-str exercises the fallback empty-body branch
            "linked_application": {
                "seen_job_id": 7,
                "job_title": "Engineer",
                "company": "ACME",
                "employer_domain": "acme.com",
            },
        },
    )
    db_session.add(row)
    db_session.flush()
    profile = ProfileService(db_session).get_for_apply(user_id)
    service = ReplyDraftService(db_session)
    ctx = service._build_context(user_id, row, profile)
    assert ctx.linked_application is not None
    assert ctx.linked_application.seen_job_id == 7
    assert ctx.inbound_body == ""


def test_resolve_provider_variants(db_session: Session) -> None:
    user_id, _job = _seed_applied_job(db_session)
    service = ReplyDraftService(db_session)
    user = service.users.get(user_id)
    assert user is not None
    with patch("app.services.reply_drafts.PlanLimitsService.allows_summaries", return_value=False):
        assert service._resolve_provider(user) == "heuristic"
    with (
        patch("app.services.reply_drafts.PlanLimitsService.allows_summaries", return_value=True),
        patch(
            "app.services.reply_drafts.resolve_ai_settings",
            return_value=SimpleNamespace(summary_provider="anthropic"),
        ),
    ):
        assert service._resolve_provider(user) == "anthropic"
    with (
        patch("app.services.reply_drafts.PlanLimitsService.allows_summaries", return_value=True),
        patch(
            "app.services.reply_drafts.resolve_ai_settings",
            return_value=SimpleNamespace(summary_provider="mystery"),
        ),
    ):
        assert service._resolve_provider(user) == "heuristic"


def test_draft_with_empty_body_raises(db_session: Session) -> None:
    user_id, _job = _seed_applied_job(db_session)
    user = ReplyDraftService(db_session).users.get(user_id)
    assert user is not None

    class EmptyDrafter:
        def draft(self, ctx: ReplyDraftContext) -> ReplyDraftResult:
            return ReplyDraftResult(subject="s", body="   ", notes="")

    service = ReplyDraftService(db_session, drafter_factory=lambda key, runtime: EmptyDrafter())
    ctx = ReplyDraftContext(
        inbound_subject="s",
        inbound_from="hr@acme.com",
        inbound_body="b",
        classification_label="follow_up",
        linked_application=None,
        profile=ProfileData(full_name="Alex"),
        mailbox_user_email="me@x.com",
    )
    with (
        patch("app.services.reply_drafts.resolve_ai_settings", return_value=SimpleNamespace()),
        pytest.raises(ValueError, match="empty body"),
    ):
        service._draft_with("heuristic", user, ctx)


def test_truncate_body_and_subject(db_session: Session) -> None:
    service = ReplyDraftService(db_session, settings=SimpleNamespace(email_draft_max_chars=10))
    assert service._truncate_body("short") == "short"
    truncated = service._truncate_body("x" * 50)
    assert truncated.endswith("…")
    assert len(truncated) <= 10

    zero = ReplyDraftService(db_session, settings=SimpleNamespace(email_draft_max_chars=0))
    assert zero._truncate_body("anything") == "anything"

    assert service._truncate_subject("short subject") == "short subject"
    long_subject = service._truncate_subject("y" * 1200)
    assert long_subject.endswith("…")
    assert len(long_subject) <= 998


def test_to_read_notes_from_non_str_payload(db_session: Session) -> None:
    user_id, _job = _seed_applied_job(db_session)
    service = ReplyDraftService(db_session)
    row = InboxReplyDraft(
        user_id=user_id,
        inbox_classification_id=1,
        message_uid=1,
        subject="Re: x",
        body_text="body",
        provider="heuristic",
        status="draft",
        payload={"notes": 12345},
    )
    db_session.add(row)
    db_session.flush()
    read = service._to_read(row)
    assert read.notes == ""


def test_default_subject_variants() -> None:
    blank = InboxClassification(
        user_id=1,
        message_uid=1,
        label="follow_up",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        subject="   ",
    )
    assert _default_subject(blank) == "Re: Your message"
    already = InboxClassification(
        user_id=1,
        message_uid=1,
        label="follow_up",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        subject="RE: existing",
    )
    assert _default_subject(already) == "RE: existing"
    fresh = InboxClassification(
        user_id=1,
        message_uid=1,
        label="follow_up",
        confidence=1.0,
        reason="r",
        provider="heuristic",
        subject="New topic",
    )
    assert _default_subject(fresh) == "Re: New topic"
