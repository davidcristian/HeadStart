"""Application-profile business logic: encrypt on write, decrypt for the owner.

A profile is a singleton per user. The structured payload is Fernet-encrypted
before storage; on read it is decrypted and returned to its owner (the data is
theirs to edit). Saving replaces the whole profile (PUT semantics). Resume files
are stored in the same encrypted blob and managed via dedicated upload/delete
endpoints.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.exceptions import ValidationError
from app.models.application_profile import ApplicationProfile
from app.repositories.profiles import ProfileRepository
from app.resumes.template_bundle import ResumeTemplateBundle, parse_template_bundle
from app.schemas.profile import (
    ALLOWED_RESUME_CONTENT_TYPES,
    ApplyProfile,
    ProfileData,
    ProfileRead,
    ResumeFileStored,
    ResumeTemplateStored,
)
from app.services.profile_resume_template import (
    build_resume_template_stored,
    validate_resume_template_upload,
)


class ProfileService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ProfileRepository(session)

    def get(self, user_id: int) -> ProfileRead:
        """The user's profile, or empty defaults (`exists=False`) if unset."""
        profile = self.repo.get(user_id)
        if profile is None:
            return ProfileRead()
        data, stored_resume, stored_template = self._decode(profile)
        resume_meta = stored_resume.to_meta() if stored_resume is not None else None
        template_meta = stored_template.to_meta() if stored_template is not None else None
        return ProfileRead(
            **data.model_dump(),
            exists=True,
            updated_at=profile.updated_at,
            resume_file=resume_meta,
            resume_template=template_meta,
        )

    def get_for_apply(self, user_id: int) -> ApplyProfile:
        """Profile with decrypted resume bytes for apply adapters."""
        profile = self.repo.get(user_id)
        if profile is None:
            return ApplyProfile()
        data, stored_resume, _stored_template = self._decode(profile)
        resume_file = stored_resume.to_resume_file() if stored_resume is not None else None
        return ApplyProfile(**data.model_dump(), exists=True, resume_file=resume_file)

    def get_resume_template_tex(self, user_id: int) -> str | None:
        """Return the user's uploaded single-file LaTeX template source, if any."""
        profile = self.repo.get(user_id)
        if profile is None:
            return None
        _data, _stored_resume, stored_template = self._decode(profile)
        if stored_template is None or stored_template.format != "single":
            return None
        return stored_template.decode_tex()

    def get_resume_template_bundle(self, user_id: int) -> ResumeTemplateBundle | None:
        """Return the user's uploaded multi-file LaTeX template bundle, if any."""
        profile = self.repo.get(user_id)
        if profile is None:
            return None
        _data, _stored_resume, stored_template = self._decode(profile)
        if stored_template is None or stored_template.format != "bundle":
            return None
        return parse_template_bundle(stored_template.decode_bundle_zip())

    def save(self, user_id: int, data: ProfileData) -> ProfileRead:
        """Create or fully replace the user's profile text fields (resume preserved)."""
        profile = self.repo.get(user_id)
        _, stored_resume, stored_template = (
            self._decode(profile) if profile is not None else (ProfileData(), None, None)
        )
        ciphertext = self._encode(data, stored_resume, stored_template)
        if profile is None:
            profile = self.repo.add(ApplicationProfile(user_id=user_id, data_ciphertext=ciphertext))
        else:
            profile.data_ciphertext = ciphertext
            self.session.flush()
        resume_meta = stored_resume.to_meta() if stored_resume is not None else None
        template_meta = stored_template.to_meta() if stored_template is not None else None
        return ProfileRead(
            **data.model_dump(),
            exists=True,
            updated_at=profile.updated_at,
            resume_file=resume_meta,
            resume_template=template_meta,
        )

    def save_resume(
        self,
        user_id: int,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> ProfileRead:
        """Store or replace the user's resume file attachment."""
        self._validate_resume_upload(filename=filename, content_type=content_type, data=data)
        stored_resume = ResumeFileStored.from_bytes(
            filename=filename,
            content_type=content_type,
            data=data,
        )
        profile = self.repo.get(user_id)
        base, _stored_resume, stored_template = (
            self._decode(profile) if profile is not None else (ProfileData(), None, None)
        )
        ciphertext = self._encode(base, stored_resume, stored_template)
        if profile is None:
            profile = self.repo.add(ApplicationProfile(user_id=user_id, data_ciphertext=ciphertext))
        else:
            profile.data_ciphertext = ciphertext
            self.session.flush()
        template_meta = stored_template.to_meta() if stored_template is not None else None
        return ProfileRead(
            **base.model_dump(),
            exists=True,
            updated_at=profile.updated_at,
            resume_file=stored_resume.to_meta(),
            resume_template=template_meta,
        )

    def save_resume_template(
        self,
        user_id: int,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> ProfileRead:
        """Store or replace the user's LaTeX resume template."""
        validate_resume_template_upload(
            filename=filename,
            content_type=content_type,
            data=data,
        )
        stored_template = build_resume_template_stored(
            filename=filename,
            content_type=content_type,
            data=data,
        )
        profile = self.repo.get(user_id)
        base, stored_resume, _stored_template = (
            self._decode(profile) if profile is not None else (ProfileData(), None, None)
        )
        ciphertext = self._encode(base, stored_resume, stored_template)
        if profile is None:
            profile = self.repo.add(ApplicationProfile(user_id=user_id, data_ciphertext=ciphertext))
        else:
            profile.data_ciphertext = ciphertext
            self.session.flush()
        return ProfileRead(
            **base.model_dump(),
            exists=True,
            updated_at=profile.updated_at,
            resume_file=stored_resume.to_meta() if stored_resume is not None else None,
            resume_template=stored_template.to_meta(),
        )

    def delete_resume_template(self, user_id: int) -> ProfileRead:
        """Remove the stored LaTeX template while keeping other profile fields."""
        profile = self.repo.get(user_id)
        if profile is None:
            return ProfileRead()
        data, stored_resume, _stored_template = self._decode(profile)
        ciphertext = self._encode(data, stored_resume, None)
        profile.data_ciphertext = ciphertext
        self.session.flush()
        return ProfileRead(
            **data.model_dump(),
            exists=True,
            updated_at=profile.updated_at,
            resume_file=stored_resume.to_meta() if stored_resume is not None else None,
            resume_template=None,
        )

    def delete_resume(self, user_id: int) -> ProfileRead:
        """Remove the stored resume file while keeping other profile fields."""
        profile = self.repo.get(user_id)
        if profile is None:
            return ProfileRead()
        data, stored_resume, stored_template = self._decode(profile)
        ciphertext = self._encode(data, None, stored_template)
        profile.data_ciphertext = ciphertext
        self.session.flush()
        return ProfileRead(
            **data.model_dump(),
            exists=True,
            updated_at=profile.updated_at,
            resume_file=None,
            resume_template=stored_template.to_meta() if stored_template is not None else None,
        )

    def delete(self, user_id: int) -> None:
        """Remove the user's profile if present (idempotent)."""
        profile = self.repo.get(user_id)
        if profile is not None:
            self.repo.delete(profile)
            self.session.flush()

    @staticmethod
    def _validate_resume_upload(*, filename: str, content_type: str, data: bytes) -> None:
        name = filename.strip()
        if not name:
            raise ValidationError("Resume filename is required")
        if content_type not in ALLOWED_RESUME_CONTENT_TYPES:
            raise ValidationError(
                "Resume must be a PDF or Word document (application/pdf, .doc, or .docx)"
            )
        max_bytes = settings.profile_resume_max_bytes
        if len(data) == 0:
            raise ValidationError("Resume file is empty")
        if len(data) > max_bytes:
            raise ValidationError(f"Resume file exceeds the {max_bytes // 1_048_576} MB limit")

    @staticmethod
    def _encode(
        data: ProfileData,
        resume: ResumeFileStored | None,
        template: ResumeTemplateStored | None,
    ) -> str:
        import json

        payload = data.model_dump()
        if resume is not None:
            payload["resume_file"] = resume.model_dump()
        if template is not None:
            payload["resume_template"] = template.model_dump()
        return encrypt(json.dumps(payload))

    @staticmethod
    def _decode(
        profile: ApplicationProfile,
    ) -> tuple[ProfileData, ResumeFileStored | None, ResumeTemplateStored | None]:
        raw = decrypt(profile.data_ciphertext)
        import json

        parsed = json.loads(raw)
        resume_raw = parsed.pop("resume_file", None)
        template_raw = parsed.pop("resume_template", None)
        data = ProfileData.model_validate(parsed)
        stored_resume = (
            ResumeFileStored.model_validate(resume_raw) if resume_raw is not None else None
        )
        stored_template = (
            ResumeTemplateStored.model_validate(template_raw) if template_raw is not None else None
        )
        return data, stored_resume, stored_template
