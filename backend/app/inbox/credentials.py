"""Mailbox credential encoding helpers (no DB session)."""

from __future__ import annotations

import json

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.inbox.types import GmailMailboxConfig, MailboxConfig
from app.models.mailbox_credential import MailboxCredential
from app.schemas.mailbox import MailboxCredentialRead


def decode_mailbox_config(credential: MailboxCredential) -> MailboxConfig | GmailMailboxConfig:
    """Decrypt and validate the stored connector config."""
    raw = json.loads(decrypt(credential.secret_ciphertext))
    if credential.connector_type == "gmail":
        return GmailMailboxConfig.model_validate(raw)
    return MailboxConfig.model_validate(raw)


def encode_mailbox_config(config: MailboxConfig | GmailMailboxConfig) -> str:
    """Encrypt a connector config for persistence."""
    return encrypt(json.dumps(config.model_dump()))


def mailbox_credential_to_read(credential: MailboxCredential) -> MailboxCredentialRead:
    """Map a credential row to the public read DTO."""
    config = decode_mailbox_config(credential)
    if isinstance(config, GmailMailboxConfig):
        return MailboxCredentialRead(
            id=credential.id,
            connector_type=credential.connector_type,
            enabled=credential.enabled,
            created_at=credential.created_at,
            has_config=True,
            email_address=config.email_address,
        )
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


def mailbox_config_for_export(credential: MailboxCredential) -> dict[str, object]:
    """Redacted mailbox config for GDPR export."""
    config = decode_mailbox_config(credential)
    if isinstance(config, GmailMailboxConfig):
        return {
            "connector_type": "gmail",
            "email_address": config.email_address,
            "access_token": "[redacted]",
            "refresh_token": "[redacted]",
        }
    return {
        "connector_type": "imap_smtp",
        **config.model_dump(exclude={"imap_password", "smtp_password"}),
        "imap_password": "[redacted]",
        "smtp_password": "[redacted]",
    }


def env_mailbox_config() -> MailboxConfig | None:
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
