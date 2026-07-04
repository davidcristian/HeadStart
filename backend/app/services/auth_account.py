"""GDPR account export and deletion helpers for AuthService."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.security import verify_password
from app.models.base import utcnow
from app.models.data_request_log import DataRequestLog
from app.models.site_credential import SiteCredential
from app.models.user import User
from app.repositories.credentials import CredentialRepository
from app.repositories.data_request_logs import DataRequestLogRepository
from app.repositories.jobs import SeenJobRepository
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.repositories.users import UserRepository
from app.schemas.auth import CredentialExport, DeleteAccountRequest, UserDataExport, UserRead
from app.schemas.job import JobRead
from app.schemas.search import SearchRead
from app.schemas.source import SourceRead
from app.schemas.target import TargetRead
from app.services.billing_account_cleanup import release_stripe_billing
from app.services.credentials import CredentialService
from app.services.profiles import ProfileService


def export_user_data(
    session: Session,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserDataExport:
    """Return a portable JSON bundle of everything the user owns."""
    user_id = user.id
    profile = ProfileService(session).get(user_id)
    credential_service = CredentialService(session)
    sources_repo = SourceRepository(session)
    searches_repo = SearchRepository(session)
    targets_repo = TargetRepository(session)
    credentials_repo = CredentialRepository(session)
    jobs_repo = SeenJobRepository(session)
    export = UserDataExport(
        exported_at=utcnow(),
        account=UserRead.model_validate(user),
        sources=[SourceRead.model_validate(row) for row in sources_repo.list_all(user_id)],
        searches=[SearchRead.model_validate(row) for row in searches_repo.list_all(user_id)],
        targets=[TargetRead.model_validate(row) for row in targets_repo.list_all(user_id)],
        credentials=[
            _credential_export(credential_service, row)
            for row in credentials_repo.list_all(user_id)
        ],
        profile=profile if profile.exists else None,
        jobs=[
            JobRead.model_validate(row) for row in jobs_repo.list_all(user_id=user_id, limit=None)
        ],
    )
    _record_data_request(
        session,
        user,
        request_type="export",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return export


def delete_user_account(
    session: Session,
    user: User,
    data: DeleteAccountRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Permanently remove the signed-in account after password confirmation."""
    repo = UserRepository(session)
    if not verify_password(data.password, user.password_hash):
        raise ValidationError("Invalid password.")
    if user.is_admin and repo.count_admins() <= 1 and repo.count() > 1:
        raise ValidationError(
            "You are the only admin. Promote another account to admin before deleting yours."
        )
    _record_data_request(
        session,
        user,
        request_type="delete",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    # Cancel Stripe billing before the local row (and Stripe IDs) disappear.
    release_stripe_billing(user)
    repo.delete(user)


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


def _record_data_request(
    session: Session,
    user: User,
    *,
    request_type: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Persist an audit row for a completed GDPR export or deletion."""
    DataRequestLogRepository(session).add(
        DataRequestLog(
            user_id=user.id if request_type == "export" else None,
            user_email=user.email,
            request_type=request_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
