"""Authentication business logic: registration, login, token refresh, password reset."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_password_reset_email
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from app.models.base import utcnow
from app.models.data_request_log import DataRequestLog
from app.models.password_reset_token import PasswordResetToken
from app.models.site_credential import SiteCredential
from app.models.user import User
from app.repositories.credentials import CredentialRepository
from app.repositories.data_request_logs import DataRequestLogRepository
from app.repositories.jobs import SeenJobRepository
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.searches import SearchRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository
from app.repositories.users import UserRepository
from app.schemas.auth import (
    CredentialExport,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserDataExport,
    UserRead,
)
from app.schemas.job import JobRead
from app.schemas.search import SearchRead
from app.schemas.source import SourceRead
from app.schemas.target import TargetRead
from app.services.credentials import CredentialService
from app.services.profiles import ProfileService

_PASSWORD_RESET_SENT_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = UserRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)
        self.sources = SourceRepository(session)
        self.searches = SearchRepository(session)
        self.targets = TargetRepository(session)
        self.credentials = CredentialRepository(session)
        self.jobs = SeenJobRepository(session)
        self.data_requests = DataRequestLogRepository(session)
        self.credential_service = CredentialService(session)
        self.profile_service = ProfileService(session)

    def register(self, data: RegisterRequest) -> User:
        """Create an account. The very first user becomes the admin."""
        email = data.email.lower()
        if self.repo.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")
        user = User(
            email=email,
            password_hash=hash_password(data.password),
            is_admin=False,
            is_active=True,
        )
        user = self.repo.add(user)
        if self.repo.claim_bootstrap_admin(user.id):
            user.is_admin = True
            self.session.flush()
        return user

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.repo.get_by_email(data.email.lower())
        # Run verify even when the user is missing to avoid leaking which emails
        # exist via response timing.
        placeholder = "$2b$12$" + "x" * 53
        if not verify_password(data.password, user.password_hash if user else placeholder):
            raise ValidationError("Invalid email or password.")
        if user is None or not user.is_active:
            raise ValidationError("Invalid email or password.")
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise ValidationError(str(exc)) from exc
        user = self.repo.get(int(payload["sub"]))
        if user is None or not user.is_active:
            raise ValidationError("Account is no longer active.")
        return self._issue_tokens(user)

    def me(self, user_id: int) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    def complete_onboarding(self, user_id: int) -> User:
        """Mark the first-run onboarding wizard as finished."""
        user = self.me(user_id)
        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = utcnow()
            self.session.flush()
        return user

    def request_password_reset(self, data: ForgotPasswordRequest) -> str:
        """Issue a reset token and email it. Always returns the same message."""
        user = self.repo.get_by_email(data.email.lower())
        if user is None or not user.is_active:
            return _PASSWORD_RESET_SENT_MESSAGE

        raw_token = generate_password_reset_token()
        expires_at = utcnow() + timedelta(minutes=settings.password_reset_expire_minutes)
        self.reset_tokens.delete_for_user(user.id)
        self.reset_tokens.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(raw_token),
                expires_at=expires_at,
            )
        )

        reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
        send_password_reset_email(to_email=user.email, reset_url=reset_url)
        return _PASSWORD_RESET_SENT_MESSAGE

    def reset_password(self, data: ResetPasswordRequest) -> None:
        """Set a new password from a valid reset token."""
        token_hash = hash_password_reset_token(data.token)
        now = utcnow()
        row = self.reset_tokens.get_valid_by_hash(token_hash, now=now)
        if row is None:
            raise ValidationError("Invalid or expired reset link. Request a new one.")

        user = self.repo.get(row.user_id)
        if user is None or not user.is_active:
            raise ValidationError("Invalid or expired reset link. Request a new one.")

        self.repo.update_password(user, hash_password(data.password))
        self.reset_tokens.delete_for_user(user.id)

    def export_data(
        self,
        user_id: int,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserDataExport:
        """Return a portable JSON bundle of everything the user owns."""
        user = self.me(user_id)
        profile = self.profile_service.get(user_id)
        export = UserDataExport(
            exported_at=utcnow(),
            account=UserRead.model_validate(user),
            sources=[SourceRead.model_validate(row) for row in self.sources.list_all(user_id)],
            searches=[SearchRead.model_validate(row) for row in self.searches.list_all(user_id)],
            targets=[TargetRead.model_validate(row) for row in self.targets.list_all(user_id)],
            credentials=[
                self._credential_export(row) for row in self.credentials.list_all(user_id)
            ],
            profile=profile if profile.exists else None,
            jobs=[
                JobRead.model_validate(row)
                for row in self.jobs.list_all(user_id=user_id, limit=None)
            ],
        )
        self._record_data_request(
            user,
            request_type="export",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return export

    def delete_account(
        self,
        user_id: int,
        data: DeleteAccountRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Permanently remove the signed-in account after password confirmation."""
        user = self.me(user_id)
        if not verify_password(data.password, user.password_hash):
            raise ValidationError("Invalid password.")
        if user.is_admin and self.repo.count_admins() <= 1 and self.repo.count() > 1:
            raise ValidationError(
                "You are the only admin. Promote another account to admin before deleting yours."
            )
        self._record_data_request(
            user,
            request_type="delete",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.repo.delete(user)

    def _credential_export(self, credential: SiteCredential) -> CredentialExport:
        payload = self.credential_service._decode(credential)
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
        self,
        user: User,
        *,
        request_type: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Persist an audit row for a completed GDPR export or deletion."""
        self.data_requests.add(
            DataRequestLog(
                user_id=user.id if request_type == "export" else None,
                user_email=user.email,
                request_type=request_type,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )

    @staticmethod
    def _issue_tokens(user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
