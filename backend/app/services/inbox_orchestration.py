"""Beat-driven inbox poll → classify → route orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.inbox.credentials import env_mailbox_config
from app.inbox.types import FetchResult, MailboxContext
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_poll_state import InboxPollStateRepository
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.repositories.users import UserRepository
from app.schemas.inbox_classification import EmailClassifyRequest
from app.schemas.inbox_reply_draft import ReplyDraftRequest
from app.services.email_classification import EmailClassificationService
from app.services.inbox import InboxService
from app.services.inbox_gate import InboxGateService
from app.services.pending_replies import PendingReplyService
from app.services.reply_drafts import DRAFTABLE_LABELS, ReplyDraftService

logger = get_logger(__name__)


@dataclass(frozen=True)
class InboxOrchestrationResult:
    """Outcome of one inbox orchestration pass across all pollable users."""

    users: int
    fetched: int
    classified: int
    skipped: int
    ignored: int
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
        self.gate = InboxGateService(session)
        self.pending_replies = PendingReplyService(session)
        self.reply_drafts = ReplyDraftService(session)

    def process_due(self) -> InboxOrchestrationResult:
        """Poll mailboxes, classify new messages, and route when configured."""
        if not settings.inbox_agent_enabled:
            return InboxOrchestrationResult(
                users=0, fetched=0, classified=0, skipped=0, ignored=0, failed=0
            )

        fetched = 0
        classified = 0
        skipped = 0
        ignored = 0
        failed = 0
        pollable = self._list_pollable_contexts()

        for user_id, ctx in pollable:
            outcome = self._process_user(user_id, ctx)
            fetched += outcome.fetched
            classified += outcome.classified
            skipped += outcome.skipped
            ignored += outcome.ignored
            failed += outcome.failed

        if pollable and (fetched or classified or ignored or failed):
            logger.info(
                (
                    "inbox orchestration: users=%d fetched=%d classified=%d "
                    "ignored=%d skipped=%d failed=%d"
                ),
                len(pollable),
                fetched,
                classified,
                ignored,
                skipped,
                failed,
            )
        return InboxOrchestrationResult(
            users=len(pollable),
            fetched=fetched,
            classified=classified,
            skipped=skipped,
            ignored=ignored,
            failed=failed,
        )

    def _candidate_user_ids(self) -> list[int]:
        """Users that may have a mailbox (enabled creds and/or shared env fallback)."""
        user_ids = {credential.user_id for credential in self.credentials.list_enabled()}
        if settings.inbox_use_env_credentials and env_mailbox_config() is not None:
            user_ids.update(user.id for user in self.users.list_all())
        return sorted(user_ids)

    def _list_pollable_contexts(self) -> list[tuple[int, MailboxContext]]:
        """Resolve each candidate mailbox once for this tick."""
        pollable: list[tuple[int, MailboxContext]] = []
        for user_id in self._candidate_user_ids():
            ctx = self.inbox.resolve_context(user_id)
            if ctx is not None:
                pollable.append((user_id, ctx))
        return pollable

    def _list_pollable_user_ids(self) -> list[int]:
        """Users with a resolvable mailbox context for polling."""
        return [user_id for user_id, _ in self._list_pollable_contexts()]

    def _process_user(self, user_id: int, ctx: MailboxContext) -> InboxOrchestrationResult:
        """Fetch and classify for one user using a pre-resolved mailbox context."""
        since_uid = self._resolve_since_uid(user_id)
        try:
            fetch_result = self.inbox.fetch_messages(
                user_id,
                since_uid=since_uid,
                limit=settings.inbox_poll_batch_size,
                ctx=ctx,
            )
        except Exception as exc:
            logger.warning("inbox fetch failed user=%s: %s", user_id, exc)
            return InboxOrchestrationResult(
                users=1, fetched=0, classified=0, skipped=0, ignored=0, failed=1
            )

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
            return InboxOrchestrationResult(
                users=1, fetched=0, classified=0, skipped=0, ignored=0, failed=0
            )

        gate_context = self.gate.build_context(user_id)
        classified = 0
        ignored = 0
        failed = 0
        last_success_uid: int | None = since_uid

        for message in messages:
            if not self.gate.should_process(user_id, message, gate_context):
                ignored += 1
                last_success_uid = message.uid
                continue
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
            self._maybe_auto_draft_reply(user_id, message.uid)

        if last_success_uid is not None and last_success_uid != since_uid:
            self.poll_state.upsert_last_polled_uid(user_id, last_success_uid)

        return InboxOrchestrationResult(
            users=1,
            fetched=len(messages),
            classified=classified,
            skipped=0,
            ignored=ignored,
            failed=failed,
        )

    def _maybe_auto_draft_reply(self, user_id: int, message_uid: int) -> None:
        """Draft and queue a delayed reply when auto-reply is enabled."""
        if not self.pending_replies.auto_reply_enabled(user_id):
            return
        row = self.classifications.get_by_user_and_uid(user_id, message_uid)
        if row is None or row.label not in DRAFTABLE_LABELS:
            return
        try:
            self.reply_drafts.draft(
                user_id,
                ReplyDraftRequest(message_uid=message_uid),
            )
        except Exception as exc:
            logger.warning(
                "inbox auto-draft failed user=%s uid=%s: %s",
                user_id,
                message_uid,
                exc,
            )
