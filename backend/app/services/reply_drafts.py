"""Draft recruiter follow-up replies for classified inbox messages."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.ai.runtime_settings import resolve_ai_settings
from app.core.config import settings as default_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.email_classifiers.types import LinkedApplicationContext
from app.models.inbox_classification import InboxClassification
from app.models.inbox_reply_draft import InboxReplyDraft
from app.models.user import User
from app.reply_drafters import ReplyDraftContext, ReplyDrafter, get_reply_drafter
from app.reply_drafters.types import ReplyDraftResult
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_reply_drafts import InboxReplyDraftRepository
from app.repositories.users import UserRepository
from app.schemas.inbox_reply_draft import ReplyDraftRead, ReplyDraftRequest
from app.schemas.profile import ProfileData
from app.services.applications import latest_live_attempt
from app.services.inbox import InboxService
from app.services.inbox_linking import linked_application_context
from app.services.plan_limits import PlanLimitsService
from app.services.profiles import ProfileService

logger = get_logger(__name__)

LLM_PROVIDERS = frozenset({"openai", "gemini", "anthropic", "llamacpp"})
DRAFTABLE_LABELS = frozenset({"follow_up", "general"})
DrafterFactory = Callable[[str, Any], ReplyDrafter]


class ReplyDraftService:
    def __init__(
        self,
        session: Session,
        *,
        drafter_factory: DrafterFactory | None = None,
        settings: Any = default_settings,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.inbox = InboxService(session)
        self.classifications = InboxClassificationRepository(session)
        self.drafts = InboxReplyDraftRepository(session)
        self._factory = drafter_factory or (
            lambda key, runtime: get_reply_drafter(key, settings=runtime)
        )
        self._settings = settings

    def draft(self, user_id: int, data: ReplyDraftRequest) -> ReplyDraftRead:
        """Draft a recruiter reply for one classified message (dry-run only)."""
        self.inbox.require_enabled()
        if not bool(getattr(self._settings, "reply_drafts_enabled", True)):
            raise ValidationError("Reply drafting is disabled")

        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        classification = self._resolve_classification(user_id, data)
        if classification.label not in DRAFTABLE_LABELS:
            raise ValidationError(
                f"Reply drafts are only supported for follow-up mail "
                f"(label={classification.label!r})"
            )

        if not data.regenerate:
            existing = self.drafts.get_by_classification(user_id, classification.id)
            if existing is not None:
                return self._to_read(existing)

        profile = ProfileService(self.session).get_for_apply(user_id)
        if not profile.exists:
            raise ValidationError("Save an application profile before drafting replies")

        ctx = self._build_context(user_id, classification, profile)
        requested = self._resolve_provider(user)
        fallback = False
        provider = requested
        notes = ""

        if requested != "heuristic":
            try:
                result = self._draft_with(requested, user, ctx)
            except Exception as exc:
                logger.warning("reply drafter provider %s failed: %s", requested, exc)
                result = self._draft_with("heuristic", user, ctx)
                provider = "heuristic"
                fallback = True
        else:
            result = self._draft_with("heuristic", user, ctx)

        notes = result.notes
        if data.regenerate:
            existing = self.drafts.get_by_classification(user_id, classification.id)
            if existing is not None:
                self.drafts.delete(existing)

        row = InboxReplyDraft(
            user_id=user_id,
            inbox_classification_id=classification.id,
            seen_job_id=classification.seen_job_id,
            message_uid=classification.message_uid,
            subject=self._truncate_subject(result.subject or _default_subject(classification)),
            body_text=self._truncate_body(result.body),
            provider=provider,
            fallback=fallback,
            status="draft",
            payload={
                "notes": notes,
                "classification_label": classification.label,
                "inbound_subject": classification.subject,
                "inbound_from": classification.from_addr,
            },
        )
        self.drafts.add(row)
        return self._to_read(row, notes=notes)

    def list_for_user(
        self,
        user_id: int,
        *,
        seen_job_id: int | None = None,
        limit: int = 50,
    ) -> list[ReplyDraftRead]:
        """Return persisted reply drafts for the user."""
        self.inbox.require_enabled()
        rows = self.drafts.list_for_user(user_id, seen_job_id=seen_job_id, limit=limit)
        return [self._to_read(row) for row in rows]

    def _resolve_classification(self, user_id: int, data: ReplyDraftRequest) -> InboxClassification:
        if data.classification_id is not None:
            row = self.classifications.get_by_id_for_user(user_id, data.classification_id)
            if row is None:
                raise NotFoundError(f"Classification {data.classification_id} not found")
            return row
        assert data.message_uid is not None
        row = self.classifications.get_by_user_and_uid(user_id, data.message_uid)
        if row is None:
            raise NotFoundError(
                f"No classification found for mailbox message uid {data.message_uid}"
            )
        return row

    def _build_context(
        self,
        user_id: int,
        classification: InboxClassification,
        profile: Any,
    ) -> ReplyDraftContext:
        body_excerpt = ""
        if classification.payload and isinstance(classification.payload.get("body_excerpt"), str):
            body_excerpt = classification.payload["body_excerpt"]
        linked_application = None
        if classification.seen_job is not None:
            raw = linked_application_context(
                classification.seen_job,
                latest_live_attempt(classification.seen_job.application_logs),
            )
            linked_application = LinkedApplicationContext.model_validate(raw)
        elif classification.payload and isinstance(
            classification.payload.get("linked_application"), dict
        ):
            linked_application = LinkedApplicationContext.model_validate(
                classification.payload["linked_application"]
            )
        return ReplyDraftContext(
            inbound_subject=classification.subject,
            inbound_from=classification.from_addr,
            inbound_body=body_excerpt,
            classification_label=classification.label,
            linked_application=linked_application,
            profile=ProfileData.model_validate(profile.model_dump()),
            mailbox_user_email=self._mailbox_user_email(user_id),
        )

    def _mailbox_user_email(self, user_id: int) -> str:
        credential = self.inbox.get_read_optional(user_id)
        if credential is not None and credential.imap_user:
            return credential.imap_user
        if self._settings.inbox_use_env_credentials and self._settings.inbox_imap_user:
            return str(self._settings.inbox_imap_user)
        return ""

    def _resolve_provider(self, user: User) -> str:
        if not PlanLimitsService(self.session).allows_summaries(user.id):
            return "heuristic"
        runtime = resolve_ai_settings(self._settings, user, "email_draft")
        provider = str(runtime.summary_provider)
        if provider in LLM_PROVIDERS:
            return provider
        return "heuristic"

    def _draft_with(self, provider: str, user: User, ctx: ReplyDraftContext) -> ReplyDraftResult:
        runtime = resolve_ai_settings(self._settings, user, "email_draft")
        drafter = self._factory(provider, runtime)
        result = drafter.draft(ctx)
        if not result.body.strip():
            raise ValueError(f"reply drafter {provider} returned empty body")
        return result

    def _truncate_body(self, text: str) -> str:
        max_chars = int(getattr(self._settings, "email_draft_max_chars", 4000))
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 1)].rstrip() + "\u2026"

    def _truncate_subject(self, text: str) -> str:
        if len(text) <= 998:
            return text
        return text[:997].rstrip() + "\u2026"

    def _to_read(self, row: InboxReplyDraft, *, notes: str | None = None) -> ReplyDraftRead:
        payload_notes = ""
        if row.payload and isinstance(row.payload.get("notes"), str):
            payload_notes = row.payload["notes"]
        return ReplyDraftRead(
            id=row.id,
            classification_id=row.inbox_classification_id,
            seen_job_id=row.seen_job_id,
            message_uid=row.message_uid,
            subject=row.subject,
            body_text=row.body_text,
            provider=row.provider,
            fallback=row.fallback,
            status=row.status,
            notes=notes if notes is not None else payload_notes,
            created_at=row.created_at,
        )


def _default_subject(classification: InboxClassification) -> str:
    subject = classification.subject.strip()
    if not subject:
        return "Re: Your message"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"
