"""Beat-driven inbox poll → classify → route orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.inbox.types import FetchResult
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_poll_state import InboxPollStateRepository
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.repositories.users import UserRepository
from app.schemas.inbox_classification import EmailClassifyRequest
from app.services.email_classification import EmailClassificationService
from app.services.inbox import InboxService

logger = get_logger(__name__)


@dataclass(frozen=True)
class InboxOrchestrationResult:
    """Outcome of one inbox orchestration pass across all pollable users."""

    users: int
    fetched: int
    classified: int
    skipped: int
    failed: int


class InboxOrchestrationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.inbox = InboxService(session)
        self.credentials = MailboxCredentialRepository(session)
        self.poll_state = InboxPollStateRepository(session)
        self.classifications = InboxClassificationRepository(session)
        self.users = UserRepository(session)
        self.classifier = EmailClassificationService(session)

    def process_due(self) -> InboxOrchestrationResult:
        """Poll mailboxes, classify new messages, and route when configured."""
        if not settings.inbox_agent_enabled:
            return InboxOrchestrationResult(users=0, fetched=0, classified=0, skipped=0, failed=0)

        fetched = 0
        classified = 0
        skipped = 0
        failed = 0
        pollable = self._list_pollable_user_ids()

        for user_id in pollable:
            outcome = self._process_user(user_id)
            fetched += outcome.fetched
            classified += outcome.classified
            skipped += outcome.skipped
            failed += outcome.failed

        if pollable and (fetched or classified or failed):
            logger.info(
                "inbox orchestration: users=%d fetched=%d classified=%d skipped=%d failed=%d",
                len(pollable),
                fetched,
                classified,
                skipped,
                failed,
            )
        return InboxOrchestrationResult(
            users=len(pollable),
            fetched=fetched,
            classified=classified,
            skipped=skipped,
            failed=failed,
        )

    def _list_pollable_user_ids(self) -> list[int]:
        """Users with a resolvable mailbox context for polling."""
        user_ids = {credential.user_id for credential in self.credentials.list_enabled()}
        if settings.inbox_use_env_credentials and InboxService._env_config() is not None:
            for user in self.users.list_all():
                if user.id in user_ids:
                    continue
                if self.inbox.resolve_context(user.id) is not None:
                    user_ids.add(user.id)
        return sorted(user_ids)

    def _process_user(self, user_id: int) -> InboxOrchestrationResult:
        if self.inbox.resolve_context(user_id) is None:
            return InboxOrchestrationResult(users=0, fetched=0, classified=0, skipped=1, failed=0)

        since_uid = self._resolve_since_uid(user_id)
        try:
            fetch_result = self.inbox.fetch_messages(
                user_id,
                since_uid=since_uid,
                limit=settings.inbox_poll_batch_size,
            )
        except Exception as exc:
            logger.warning("inbox fetch failed user=%s: %s", user_id, exc)
            return InboxOrchestrationResult(users=1, fetched=0, classified=0, skipped=0, failed=1)

        return self._classify_fetched(user_id, fetch_result, since_uid=since_uid)

    def _resolve_since_uid(self, user_id: int) -> int | None:
        """Return the UID cursor; bootstrap from persisted classifications when unset."""
        stored = self.poll_state.get_last_polled_uid(user_id)
        if stored is not None:
            return stored
        return self.classifications.max_message_uid_for_user(user_id)

    def _classify_fetched(
        self,
        user_id: int,
        fetch_result: FetchResult,
        *,
        since_uid: int | None,
    ) -> InboxOrchestrationResult:
        messages = sorted(fetch_result.messages, key=lambda message: message.uid)
        if not messages:
            if fetch_result.max_uid is not None and fetch_result.max_uid != since_uid:
                self.poll_state.upsert_last_polled_uid(user_id, fetch_result.max_uid)
            return InboxOrchestrationResult(users=1, fetched=0, classified=0, skipped=0, failed=0)

        classified = 0
        failed = 0
        last_success_uid: int | None = since_uid

        for message in messages:
            try:
                self.classifier.classify(
                    user_id,
                    EmailClassifyRequest(message=message),
                )
            except Exception as exc:
                logger.warning(
                    "inbox classify failed user=%s uid=%s: %s",
                    user_id,
                    message.uid,
                    exc,
                )
                failed += 1
                break
            classified += 1
            last_success_uid = message.uid

        if last_success_uid is not None and last_success_uid != since_uid:
            self.poll_state.upsert_last_polled_uid(user_id, last_success_uid)

        return InboxOrchestrationResult(
            users=1,
            fetched=len(messages),
            classified=classified,
            skipped=0,
            failed=failed,
        )
