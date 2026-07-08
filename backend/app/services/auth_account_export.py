"""Assemble the GDPR portable export bundle for a user."""

from __future__ import annotations

import base64

from sqlalchemy.orm import Session

from app.inbox.credentials import mailbox_config_for_export
from app.models.base import utcnow
from app.models.site_credential import SiteCredential
from app.models.user import User
from app.repositories.application_artifacts import ApplicationArtifactRepository
from app.repositories.credentials import CredentialRepository
from app.repositories.deliveries import DeliveryLogRepository
from app.repositories.inbox_classifications import InboxClassificationRepository
from app.repositories.inbox_pending_replies import InboxPendingReplyRepository
from app.repositories.inbox_reply_drafts import InboxReplyDraftRepository
from app.repositories.inbox_reply_send_logs import InboxReplySendLogRepository
from app.repositories.jobs import DEFAULT_EXPORT_JOBS_CHUNK_SIZE, SeenJobRepository
from app.repositories.mailbox_credentials import MailboxCredentialRepository
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.schemas.auth import CredentialExport, UserDataExport, UserRead
from app.schemas.auth_export import (
    ApplicationArtifactExport,
    DeliveryLogExport,
    InboxClassificationExport,
    InboxPendingReplyExport,
    InboxReplyDraftExport,
    InboxReplySendLogExport,
    MailboxCredentialExport,
    ProfileFileExport,
)
from app.schemas.job import JobRead
from app.schemas.promo import PromoRedemptionRead
from app.schemas.search import SearchRead
from app.schemas.source import SourceRead
from app.schemas.target import TargetRead
from app.services.application_artifacts import ApplicationArtifactService
from app.services.application_logs import ApplicationLogService
from app.services.credentials import CredentialService
from app.services.profiles import ProfileService


def build_user_data_export(
    session: Session,
    user: User,
    *,
    jobs_chunk_size: int = DEFAULT_EXPORT_JOBS_CHUNK_SIZE,
) -> UserDataExport:
    """Collect every user-owned entity into a portable JSON-ready bundle."""
    user_id = user.id
    profile_service = ProfileService(session)
    profile = profile_service.get(user_id)
    resume_stored, template_stored = profile_service.get_stored_files(user_id)
    credential_service = CredentialService(session)

    return UserDataExport(
        exported_at=utcnow(),
        account=UserRead.model_validate(user),
        sources=[
            SourceRead.model_validate(row) for row in SourceRepository(session).list_all(user_id)
        ],
        searches=[
            SearchRead.model_validate(row) for row in SearchRepository(session).list_all(user_id)
        ],
        targets=[
            TargetRead.model_validate(row) for row in TargetRepository(session).list_all(user_id)
        ],
        credentials=[
            _credential_export(credential_service, row)
            for row in CredentialRepository(session).list_all(user_id)
        ],
        profile=profile if profile.exists else None,
        resume_file=(
            ProfileFileExport(
                filename=resume_stored.filename,
                content_type=resume_stored.content_type,
                data_b64=resume_stored.data_b64,
            )
            if resume_stored is not None
            else None
        ),
        resume_template=(
            ProfileFileExport(
                filename=template_stored.filename,
                data_b64=template_stored.data_b64,
                format=template_stored.format,
                entrypoint=template_stored.entrypoint,
                file_count=template_stored.file_count,
            )
            if template_stored is not None
            else None
        ),
        jobs=_job_exports(session, user_id, chunk_size=jobs_chunk_size),
        applications=ApplicationLogService(session).list_for_user(user_id, limit=None),
        artifacts=_artifact_exports(session, user_id),
        deliveries=[
            DeliveryLogExport.model_validate(row)
            for row in DeliveryLogRepository(session).list_all_for_user(user_id)
        ],
        mailbox=_mailbox_export(session, user_id),
        inbox_classifications=[
            InboxClassificationExport.model_validate(row)
            for row in InboxClassificationRepository(session).list_for_user(user_id, limit=None)
        ],
        inbox_reply_drafts=[
            InboxReplyDraftExport.model_validate(row)
            for row in InboxReplyDraftRepository(session).list_for_user(user_id, limit=None)
        ],
        inbox_pending_replies=[
            InboxPendingReplyExport.model_validate(row)
            for row in InboxPendingReplyRepository(session).list_for_user(user_id)
        ],
        inbox_reply_send_logs=[
            InboxReplySendLogExport.model_validate(row)
            for row in InboxReplySendLogRepository(session).list_for_user(user_id, limit=None)
        ],
        promo_redemptions=[
            PromoRedemptionRead.model_validate(row)
            for row in PromoCodeRepository(session).list_redemptions_for_user(user_id)
        ],
    )


def _job_exports(
    session: Session,
    user_id: int,
    *,
    chunk_size: int = DEFAULT_EXPORT_JOBS_CHUNK_SIZE,
) -> list[JobRead]:
    """Serialize job history in keyset pages so export never issues one unbounded SELECT."""
    jobs: list[JobRead] = []
    for row in SeenJobRepository(session).iter_for_user(user_id, chunk_size=chunk_size):
        jobs.append(JobRead.model_validate(row))
        # Drop the ORM instance so peak identity-map memory stays O(chunk_size).
        session.expunge(row)
    return jobs


def _artifact_exports(session: Session, user_id: int) -> list[ApplicationArtifactExport]:
    artifacts = ApplicationArtifactRepository(session).list_all_for_user(user_id)
    decrypt = ApplicationArtifactService._decrypt_bytes
    return [
        ApplicationArtifactExport(
            id=row.id,
            artifact_type=row.artifact_type,
            filename=row.filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            content_sha256=row.content_sha256,
            created_at=row.created_at,
            data_b64=base64.b64encode(decrypt(row.data_ciphertext)).decode("ascii"),
        )
        for row in artifacts
    ]


def _mailbox_export(session: Session, user_id: int) -> MailboxCredentialExport | None:
    credential = MailboxCredentialRepository(session).get_for_user(user_id)
    if credential is None:
        return None
    return MailboxCredentialExport(
        id=credential.id,
        connector_type=credential.connector_type,
        enabled=credential.enabled,
        created_at=credential.created_at,
        config=mailbox_config_for_export(credential),
    )


def _credential_export(
    credential_service: CredentialService, credential: SiteCredential
) -> CredentialExport:
    payload = credential_service._decode(credential)
    return CredentialExport(
        id=credential.id,
        source_id=credential.source_id,
        name=credential.name,
        enabled=credential.enabled,
        created_at=credential.created_at,
        cookies=payload["cookies"],
        headers=payload["headers"],
        session=payload["session"],
    )
