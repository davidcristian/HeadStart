"""Inbox mailbox business logic: encrypt credentials, resolve connectors, fetch/send."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.exceptions import NotFoundError, ValidationError
from app.inbox.base import get_mailbox
from app.inbox.types import (
    FetchResult,
    MailboxConfig,
    MailboxContext,
    OutboundMessage,
    SendResult,
)
from app.models.mailbox_credential import MailboxCredential
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.schemas.mailbox import MailboxCredentialRead, MailboxCredentialUpsert, MailboxTestResponse


class InboxNotEnabledError(ValidationError):
    """Raised when inbox automation is disabled in this deployment."""


class InboxService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = MailboxCredentialRepository(session)

    def require_enabled(self) -> None:
        """Gate inbox APIs and worker tasks on the deployment flag."""
        if not settings.inbox_agent_enabled:
            raise InboxNotEnabledError(
                "Inbox automation is disabled on this deployment "
                "(set INBOX_AGENT_ENABLED=true for local dev)."
            )

    def get_read(self, user_id: int) -> MailboxCredentialRead:
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            raise NotFoundError("Mailbox credentials are not configured")
        return self.to_read(credential)

    def get_read_optional(self, user_id: int) -> MailboxCredentialRead | None:
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            return None
        return self.to_read(credential)

    def upsert(self, user_id: int, data: MailboxCredentialUpsert) -> MailboxCredentialRead:
        self.require_enabled()
        self._validate_connector_type(data.connector_type)
        payload = data.config.model_dump()
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            credential = MailboxCredential(
                user_id=user_id,
                connector_type=data.connector_type,
                enabled=data.enabled,
                secret_ciphertext=encrypt(json.dumps(payload)),
            )
            self.repo.add(credential)
        else:
            credential.connector_type = data.connector_type
            credential.enabled = data.enabled
            credential.secret_ciphertext = encrypt(json.dumps(payload))
            self.session.flush()
        return self.to_read(credential)

    def delete(self, user_id: int) -> None:
        self.require_enabled()
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            raise NotFoundError("Mailbox credentials are not configured")
        self.repo.delete(credential)
        self.session.flush()

    def test_connection(
        self, user_id: int, config: MailboxConfig | None = None
    ) -> MailboxTestResponse:
        self.require_enabled()
        ctx = (
            self._context_from_config(user_id, config) if config else self.resolve_context(user_id)
        )
        if ctx is None:
            raise ValidationError("No mailbox credentials configured")
        result = get_mailbox(ctx.connector_type).test_connection(ctx)
        return MailboxTestResponse(
            imap_ok=result.imap_ok,
            smtp_ok=result.smtp_ok,
            error=result.error,
        )

    def fetch_messages(
        self, user_id: int, *, since_uid: int | None = None, limit: int = 50
    ) -> FetchResult:
        self.require_enabled()
        ctx = self.resolve_context(user_id)
        if ctx is None:
            raise ValidationError("No mailbox credentials configured")
        return get_mailbox(ctx.connector_type).fetch_messages(ctx, since_uid=since_uid, limit=limit)

    def send_message(self, user_id: int, message: OutboundMessage) -> SendResult:
        self.require_enabled()
        ctx = self.resolve_context(user_id)
        if ctx is None:
            raise ValidationError("No mailbox credentials configured")
        return get_mailbox(ctx.connector_type).send_message(ctx, message)

    def resolve_context(self, user_id: int) -> MailboxContext | None:
        """Return a connector context for the user, or None when unconfigured."""
        credential = self.repo.get_for_user(user_id)
        if credential is not None and credential.enabled:
            config = self._decode_config(credential)
            return MailboxContext(
                connector_type=credential.connector_type,
                config=config,
                user_id=user_id,
            )
        env_config = self._env_config()
        if env_config is not None:
            return MailboxContext(
                connector_type="imap_smtp",
                config=env_config,
                user_id=user_id,
            )
        return None

    def config_for_export(self, user_id: int) -> MailboxConfig | None:
        """Decrypted mailbox config for GDPR export, when present."""
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            return None
        return self._decode_config(credential)

    @staticmethod
    def to_read(credential: MailboxCredential) -> MailboxCredentialRead:
        config = InboxService._decode_config(credential)
        return MailboxCredentialRead(
            id=credential.id,
            connector_type=credential.connector_type,
            enabled=credential.enabled,
            created_at=credential.created_at,
            has_config=True,
            imap_host=config.imap_host,
            smtp_host=config.smtp_host,
            imap_user=config.imap_user,
        )

    @staticmethod
    def _decode_config(credential: MailboxCredential) -> MailboxConfig:
        raw = json.loads(decrypt(credential.secret_ciphertext))
        return MailboxConfig.model_validate(raw)

    @staticmethod
    def _validate_connector_type(connector_type: str) -> None:
        from app.inbox.base import available_mailboxes

        if connector_type not in available_mailboxes():
            raise ValidationError(f"Unknown mailbox connector '{connector_type}'")

    @staticmethod
    def _context_from_config(user_id: int, config: MailboxConfig) -> MailboxContext:
        return MailboxContext(connector_type="imap_smtp", config=config, user_id=user_id)

    @staticmethod
    def _env_config() -> MailboxConfig | None:
        """Dev-only fallback when INBOX_USE_ENV_CREDENTIALS=true and vars are set."""
        if not settings.inbox_use_env_credentials:
            return None
        required = (
            settings.inbox_imap_host,
            settings.inbox_imap_user,
            settings.inbox_imap_password,
            settings.inbox_smtp_host,
        )
        if not all(required):
            return None
        return MailboxConfig(
            imap_host=settings.inbox_imap_host,
            imap_port=settings.inbox_imap_port,
            imap_use_ssl=settings.inbox_imap_use_ssl,
            imap_user=settings.inbox_imap_user,
            imap_password=settings.inbox_imap_password,
            imap_mailbox=settings.inbox_imap_mailbox,
            smtp_host=settings.inbox_smtp_host,
            smtp_port=settings.inbox_smtp_port,
            smtp_use_tls=settings.inbox_smtp_use_tls,
            smtp_user=settings.inbox_smtp_user,
            smtp_password=settings.inbox_smtp_password,
            smtp_from=settings.inbox_smtp_from,
        )
