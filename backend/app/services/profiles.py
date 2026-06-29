"""Application-profile business logic: encrypt on write, decrypt for the owner.

A profile is a singleton per user. The structured payload is Fernet-encrypted
before storage; on read it is decrypted and returned to its owner (the data is
theirs to edit). Saving replaces the whole profile (PUT semantics).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.models.application_profile import ApplicationProfile
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import ProfileData, ProfileRead


class ProfileService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ProfileRepository(session)

    def get(self, user_id: int) -> ProfileRead:
        """The user's profile, or empty defaults (`exists=False`) if unset."""
        profile = self.repo.get(user_id)
        if profile is None:
            return ProfileRead()
        data = self._decode(profile)
        return ProfileRead(**data.model_dump(), exists=True, updated_at=profile.updated_at)

    def save(self, user_id: int, data: ProfileData) -> ProfileRead:
        """Create or fully replace the user's profile."""
        ciphertext = encrypt(data.model_dump_json())
        profile = self.repo.get(user_id)
        if profile is None:
            profile = self.repo.add(ApplicationProfile(user_id=user_id, data_ciphertext=ciphertext))
        else:
            profile.data_ciphertext = ciphertext
            self.session.flush()
        return ProfileRead(**data.model_dump(), exists=True, updated_at=profile.updated_at)

    def delete(self, user_id: int) -> None:
        """Remove the user's profile if present (idempotent)."""
        profile = self.repo.get(user_id)
        if profile is not None:
            self.repo.delete(profile)
            self.session.flush()

    @staticmethod
    def _decode(profile: ApplicationProfile) -> ProfileData:
        return ProfileData.model_validate_json(decrypt(profile.data_ciphertext))
