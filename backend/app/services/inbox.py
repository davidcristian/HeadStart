"""Inbox mailbox business logic: encrypt credentials, resolve connectors, fetch/send."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.inbox.base import get_mailbox
from app.inbox.credentials import (
    decode_mailbox_config,
    encode_mailbox_config,
    env_mailbox_config,
    mailbox_config_for_export,
    mailbox_credential_to_read,
)
from app.inbox.mailbox_email import mailbox_email_from_read
from app.inbox.types import (
    FastmailMailboxConfig,
    FetchResult,
    GmailMailboxConfig,
    MailboxConfig,
    MailboxContext,
    OutboundMessage,
    OutlookMailboxConfig,
    SendResult,
    YahooMailboxConfig,
)
from app.models.mailbox_credential import MailboxCredential
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.schemas.mailbox import (
    GmailAuthorizeResponse,
    GmailOAuthCallbackResult,
    MailboxCredentialRead,
    MailboxCredentialUpsert,
    MailboxTestResponse,
    OutlookAuthorizeResponse,
    YahooAuthorizeResponse,
)
from app.services import inbox_mailbox_oauth
from app.services.inbox_oauth import (
    ensure_fresh_gmail_config,
    ensure_fresh_outlook_config,
    ensure_fresh_yahoo_config,
)


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
        return mailbox_credential_to_read(credential)

    def get_read_optional(self, user_id: int) -> MailboxCredentialRead | None:
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            return None
        return mailbox_credential_to_read(credential)

    def upsert(self, user_id: int, data: MailboxCredentialUpsert) -> MailboxCredentialRead:
        self.require_enabled()
        if data.connector_type not in {"imap_smtp", "fastmail"}:
            raise ValidationError(
                "Manual credential upsert supports imap_smtp and fastmail only. "
                "Connect Gmail via GET /inbox/gmail/authorize, Outlook via "
                "GET /inbox/outlook/authorize, or Yahoo via GET /inbox/yahoo/authorize."
            )
        self._validate_connector_type(data.connector_type)
        credential = self.repo.get_for_user(user_id)
        ciphertext = encode_mailbox_config(data.config)
        if credential is None:
            credential = MailboxCredential(
                user_id=user_id,
                connector_type=data.connector_type,
                enabled=data.enabled,
                secret_ciphertext=ciphertext,
            )
            self.repo.add(credential)
        else:
            credential.connector_type = data.connector_type
            credential.enabled = data.enabled
            credential.secret_ciphertext = ciphertext
            self.session.flush()
        return mailbox_credential_to_read(credential)

    def delete(self, user_id: int) -> None:
        self.require_enabled()
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            raise NotFoundError("Mailbox credentials are not configured")
        self.repo.delete(credential)
        self.session.flush()

    def gmail_authorize_url(self, user_id: int) -> tuple[GmailAuthorizeResponse, str]:
        """Return a Google OAuth consent URL and the browser-bound nonce."""
        self.require_enabled()
        return inbox_mailbox_oauth.gmail_authorize_url(user_id)

    def complete_gmail_oauth(
        self, *, code: str, state: str, oauth_nonce: str | None
    ) -> GmailOAuthCallbackResult:
        """Exchange an OAuth callback for encrypted Gmail credentials."""
        self.require_enabled()
        return inbox_mailbox_oauth.complete_gmail_oauth(
            self.session,
            self.repo,
            code=code,
            state=state,
            oauth_nonce=oauth_nonce,
        )

    @staticmethod
    def gmail_oauth_available() -> bool:
        """Whether the deployment exposes Gmail OAuth connect."""
        return inbox_mailbox_oauth.gmail_oauth_available()

    @staticmethod
    def outlook_oauth_available() -> bool:
        """Whether the deployment exposes Outlook OAuth connect."""
        return inbox_mailbox_oauth.outlook_oauth_available()

    @staticmethod
    def yahoo_oauth_available() -> bool:
        """Whether the deployment exposes Yahoo OAuth connect."""
        return inbox_mailbox_oauth.yahoo_oauth_available()

    def outlook_authorize_url(self, user_id: int) -> tuple[OutlookAuthorizeResponse, str]:
        """Return a Microsoft OAuth consent URL and the browser-bound nonce."""
        self.require_enabled()
        return inbox_mailbox_oauth.outlook_authorize_url(user_id)

    def complete_outlook_oauth(
        self, *, code: str, state: str, oauth_nonce: str | None
    ) -> GmailOAuthCallbackResult:
        """Exchange an OAuth callback for encrypted Outlook credentials."""
        self.require_enabled()
        return inbox_mailbox_oauth.complete_outlook_oauth(
            self.session,
            self.repo,
            code=code,
            state=state,
            oauth_nonce=oauth_nonce,
        )

    def yahoo_authorize_url(self, user_id: int) -> tuple[YahooAuthorizeResponse, str]:
        """Return a Yahoo OAuth consent URL and the browser-bound nonce."""
        self.require_enabled()
        return inbox_mailbox_oauth.yahoo_authorize_url(user_id)

    def complete_yahoo_oauth(
        self, *, code: str, state: str, oauth_nonce: str | None
    ) -> GmailOAuthCallbackResult:
        """Exchange an OAuth callback for encrypted Yahoo credentials."""
        self.require_enabled()
        return inbox_mailbox_oauth.complete_yahoo_oauth(
            self.session,
            self.repo,
            code=code,
            state=state,
            oauth_nonce=oauth_nonce,
        )

    def test_connection(
        self,
        user_id: int,
        *,
        connector_type: str = "imap_smtp",
        config: MailboxConfig | FastmailMailboxConfig | None = None,
    ) -> MailboxTestResponse:
        self.require_enabled()
        ctx = (
            self._context_from_config(user_id, connector_type, config)
            if config is not None
            else self.resolve_context(user_id)
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
        self,
        user_id: int,
        *,
        since_uid: int | None = None,
        limit: int = 50,
        ctx: MailboxContext | None = None,
    ) -> FetchResult:
        """Fetch inbound mail; pass ``ctx`` when the caller already resolved it (INB-20)."""
        self.require_enabled()
        resolved = ctx if ctx is not None else self.resolve_context(user_id)
        if resolved is None:
            raise ValidationError("No mailbox credentials configured")
        return get_mailbox(resolved.connector_type).fetch_messages(
            resolved, since_uid=since_uid, limit=limit
        )

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
            config = decode_mailbox_config(credential)
            if credential.connector_type == "gmail":
                if not isinstance(config, GmailMailboxConfig):
                    raise ValidationError("Stored Gmail credential is invalid")
                config = ensure_fresh_gmail_config(self.session, credential, config)
            elif credential.connector_type == "outlook":
                if not isinstance(config, OutlookMailboxConfig):
                    raise ValidationError("Stored Outlook credential is invalid")
                config = ensure_fresh_outlook_config(self.session, credential, config)
            elif credential.connector_type == "yahoo":
                if not isinstance(config, YahooMailboxConfig):
                    raise ValidationError("Stored Yahoo credential is invalid")
                config = ensure_fresh_yahoo_config(self.session, credential, config)
            return MailboxContext(
                connector_type=credential.connector_type,
                config=config,
                user_id=user_id,
            )
        env_config = env_mailbox_config()
        if env_config is not None:
            return MailboxContext(
                connector_type="imap_smtp",
                config=env_config,
                user_id=user_id,
            )
        return None

    def mailbox_user_email(self, user_id: int) -> str:
        """Return the connected mailbox address for classification and gating."""
        read = self.get_read_optional(user_id)
        if read is not None:
            return mailbox_email_from_read(
                connector_type=read.connector_type,
                imap_user=read.imap_user,
                email_address=read.email_address,
            )
        if settings.inbox_use_env_credentials and settings.inbox_imap_user:
            return str(settings.inbox_imap_user)
        return ""

    def config_for_export(self, user_id: int) -> dict[str, object] | None:
        """Decrypted mailbox config for GDPR export, when present (secrets redacted)."""
        credential = self.repo.get_for_user(user_id)
        if credential is None:
            return None
        return mailbox_config_for_export(credential)

    @staticmethod
    def _validate_connector_type(connector_type: str) -> None:
        from app.inbox.base import available_mailboxes

        if connector_type not in available_mailboxes():
            raise ValidationError(f"Unknown mailbox connector '{connector_type}'")

    @staticmethod
    def _context_from_config(
        user_id: int,
        connector_type: str,
        config: MailboxConfig | FastmailMailboxConfig,
    ) -> MailboxContext:
        return MailboxContext(connector_type=connector_type, config=config, user_id=user_id)
