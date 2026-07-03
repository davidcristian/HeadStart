"""Classify inbound recruiter email and persist results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sqlalchemy.orm import Session

from app.ai.runtime_settings import resolve_ai_settings
from app.core.config import settings as default_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.email_classifiers import (
    EmailClassifier,
    EmailClassifyContext,
    LinkedApplicationContext,
    get_email_classifier,
)
from app.email_classifiers.sanitize import prepare_message
from app.inbox.types import InboxMessage
from app.models.inbox_classification import InboxClassification
from app.models.seen_job import SeenJob
from app.models.user import User
from app.repositories.applications import ApplicationPipelineRepository
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.users import UserRepository
from app.schemas.inbox_classification import (
    EmailClassificationLabelRead,
    EmailClassificationRead,
    EmailClassifyRequest,
    LinkedApplicationRead,
)
from app.services.applications import latest_live_attempt
from app.services.ghost_recovery import GhostRecoveryService
from app.services.inbox import InboxService
from app.services.interview_handoff import InterviewHandoffService
from app.services.inbox_linking import link_message_to_job, linked_application_context
from app.services.inbox_routing import InboxRoutingService
from app.services.plan_limits import PlanLimitsService

logger = get_logger(__name__)

LLM_PROVIDERS = frozenset({"openai", "gemini", "anthropic", "llamacpp"})
ClassifierFactory = Callable[[str, Any], EmailClassifier]


class EmailClassificationService:
    def __init__(
        self,
        session: Session,
        *,
        classifier_factory: ClassifierFactory | None = None,
        settings: Any = default_settings,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.inbox = InboxService(session)
        self.routing = InboxRoutingService(session)
        self.pipeline = ApplicationPipelineRepository(session)
        self.ghost_recovery = GhostRecoveryService(session)
        self.interview_handoff = InterviewHandoffService(session)
        self.classifications = InboxClassificationRepository(session)
        self._factory = classifier_factory or (
            lambda key, runtime: get_email_classifier(key, settings=runtime)
        )
        self._settings = settings

    def classify(self, user_id: int, data: EmailClassifyRequest) -> EmailClassificationRead:
        """Classify one inbound message, link it to an application, and persist."""
        self.inbox.require_enabled()
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        message = self._resolve_message(user_id, data)
        existing = self.classifications.get_by_user_and_uid(user_id, message.uid)
        if existing is not None:
            return self._to_read(existing)

        linked_job = self._link_job(user_id, message)
        ctx = self._build_context(user_id, message, linked_job)
        requested = self._resolve_provider(user)
        fallback = False
        provider = requested

        if requested != "heuristic":
            try:
                result = self._classify_with(requested, user, ctx)
            except Exception as exc:
                logger.warning("email classifier provider %s failed: %s", requested, exc)
                result = self._classify_with("heuristic", user, ctx)
                provider = "heuristic"
                fallback = True
        else:
            result = self._classify_with("heuristic", user, ctx)

        linked_payload = None
        if linked_job is not None:
            linked_payload = linked_application_context(
                linked_job,
                latest_live_attempt(linked_job.application_logs),
            )
        row = InboxClassification(
            user_id=user_id,
            seen_job_id=linked_job.id if linked_job is not None else None,
            message_uid=message.uid,
            message_id=message.message_id,
            label=result.label,
            confidence=result.confidence,
            reason=result.reason,
            provider=provider,
            fallback=fallback,
            subject=message.subject,
            from_addr=message.from_addr,
            payload={
                "body_excerpt": message.body_text[:500],
                "linked_application": linked_payload,
            },
        )
        self.classifications.add(row)
        if linked_job is not None:
            row.seen_job = linked_job
            self.ghost_recovery.maybe_recover_from_classification(user_id, linked_job, row)
            self.interview_handoff.maybe_handoff_from_classification(user_id, linked_job, row)
        self.routing.route_after_classify(user_id, row)
        return self._to_read(row)

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[EmailClassificationRead]:
        """Return recent persisted classifications for the user."""
        self.inbox.require_enabled()
        rows = self.classifications.list_for_user(user_id, limit=limit)
        return [self._to_read(row) for row in rows]

    def _resolve_message(self, user_id: int, data: EmailClassifyRequest) -> InboxMessage:
        if data.message is not None:
            return data.message
        assert data.uid is not None
        fetched = self.inbox.fetch_messages(user_id, since_uid=data.uid - 1, limit=100)
        for message in fetched.messages:
            if message.uid == data.uid:
                return message
        raise NotFoundError(f"Mailbox message uid {data.uid} not found")

    def _link_job(self, user_id: int, message: InboxMessage) -> SeenJob | None:
        jobs = self.pipeline.list_jobs_for_user(user_id, limit=200)
        return link_message_to_job(message, jobs)

    def _build_context(
        self, user_id: int, message: InboxMessage, linked_job: SeenJob | None
    ) -> EmailClassifyContext:
        max_chars = int(getattr(self._settings, "email_classify_max_body_chars", 8000))
        sanitized = prepare_message(message, max_chars=max_chars)
        linked_application = None
        if linked_job is not None:
            raw = linked_application_context(
                linked_job, latest_live_attempt(linked_job.application_logs)
            )
            linked_application = LinkedApplicationContext.model_validate(raw)
        return EmailClassifyContext(
            message=sanitized,
            linked_application=linked_application,
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
        runtime = resolve_ai_settings(self._settings, user, "email_classify")
        provider = str(runtime.summary_provider)
        if provider in LLM_PROVIDERS:
            return provider
        return "heuristic"

    def _classify_with(self, provider: str, user: User, ctx: EmailClassifyContext) -> Any:
        runtime = resolve_ai_settings(self._settings, user, "email_classify")
        classifier = self._factory(provider, runtime)
        return classifier.classify(ctx)

    def _to_read(self, row: InboxClassification) -> EmailClassificationRead:
        linked = None
        if row.seen_job_id is not None and row.seen_job is not None:
            linked = LinkedApplicationRead(
                seen_job_id=row.seen_job_id,
                job_title=row.seen_job.title,
                company=row.seen_job.company,
            )
        elif row.payload and isinstance(row.payload.get("linked_application"), dict):
            raw = row.payload["linked_application"]
            linked = LinkedApplicationRead(
                seen_job_id=int(raw["seen_job_id"]),
                job_title=str(raw.get("job_title", "")),
                company=str(raw.get("company", "")),
            )
        return EmailClassificationRead(
            id=row.id,
            message_uid=row.message_uid,
            message_id=row.message_id,
            label=cast(EmailClassificationLabelRead, row.label),
            confidence=row.confidence,
            reason=row.reason,
            provider=row.provider,
            fallback=row.fallback,
            subject=row.subject,
            from_addr=row.from_addr,
            linked_application=linked,
            routed_to=row.routed_to,
            routing_status=row.routing_status,
            routing_error=row.routing_error,
            created_at=row.created_at,
        )
