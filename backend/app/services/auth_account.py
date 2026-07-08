"""GDPR account export and deletion helpers for AuthService."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.auth_events import log_auth_event
from app.core.exceptions import ValidationError
from app.core.security import pseudonymize_email_for_audit, verify_password
from app.models.data_request_log import DataRequestLog
from app.models.user import User
from app.repositories.data_request_logs import DataRequestLogRepository
from app.repositories.users import UserRepository
from app.schemas.auth import DeleteAccountRequest, UserDataExport
from app.services.auth_account_export import build_user_data_export
from app.services.billing_account_cleanup import release_stripe_billing
from app.services.mailbox_account_cleanup import release_mailbox_oauth


def export_user_data(
    session: Session,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserDataExport:
    """Return a portable JSON bundle of everything the user owns."""
    export = build_user_data_export(session, user)
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
    # Cancel Stripe billing and revoke mailbox OAuth before the local row
    # (and encrypted tokens) disappear.
    release_stripe_billing(user)
    release_mailbox_oauth(session, user.id)
    log_auth_event(
        "account_deleted",
        email=user.email,
        user_id=user.id,
        ip_address=ip_address,
    )
    repo.delete(user)


def _record_data_request(
    session: Session,
    user: User,
    *,
    request_type: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Persist an audit row for a completed GDPR export or deletion."""
    repo = DataRequestLogRepository(session)
    if request_type == "delete":
        # Deletion must not leave recoverable email/IP/UA after the account is gone.
        pseudonym = pseudonymize_email_for_audit(user.email)
        repo.redact_for_erasure(user.id, email_pseudonym=pseudonym)
        repo.add(
            DataRequestLog(
                user_id=None,
                user_email=pseudonym,
                request_type="delete",
                ip_address=None,
                user_agent=None,
            )
        )
        return
    repo.add(
        DataRequestLog(
            user_id=user.id,
            user_email=user.email,
            request_type=request_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
