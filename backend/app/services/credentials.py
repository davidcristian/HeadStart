"""Site credential business logic: encrypt on write, decrypt only at the edge.

The secret payload is a JSON object `{"cookies": {...}, "headers": {...},
"session": {...}}` which is Fernet-encrypted before storage. Read responses
never expose the secret material, only booleans describing what is present.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.core.exceptions import NotFoundError, ValidationError
from app.models.site_credential import SiteCredential
from app.repositories.credentials import CredentialRepository
from app.repositories.sources import SourceRepository
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialUpdate
from app.services.plan_limits import PlanLimitsService

_SECTIONS = ("cookies", "headers", "session")


class CredentialService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = CredentialRepository(session)
        self.sources = SourceRepository(session)

    def list_all(self, user_id: int) -> list[CredentialRead]:
        return [self.to_read(c) for c in self.repo.list_all(user_id)]

    def get(self, credential_id: int, user_id: int) -> SiteCredential:
        credential = self.repo.get(credential_id, user_id)
        if credential is None:
            raise NotFoundError(f"Credential {credential_id} not found")
        return credential

    def get_read(self, credential_id: int, user_id: int) -> CredentialRead:
        return self.to_read(self.get(credential_id, user_id))

    def create(self, user_id: int, data: CredentialCreate) -> CredentialRead:
        PlanLimitsService(self.session).require_site_credentials(user_id)
        if self.sources.get(data.source_id, user_id) is None:
            raise ValidationError(f"Source {data.source_id} does not exist")
        payload = {"cookies": data.cookies, "headers": data.headers, "session": data.session}
        credential = SiteCredential(
            user_id=user_id,
            source_id=data.source_id,
            name=data.name,
            enabled=data.enabled,
            secret_ciphertext=encrypt(json.dumps(payload)),
        )
        return self.to_read(self.repo.add(credential))

    def update(self, credential_id: int, user_id: int, data: CredentialUpdate) -> CredentialRead:
        credential = self.get(credential_id, user_id)
        fields = data.model_dump(exclude_unset=True)

        if "name" in fields:
            credential.name = fields["name"]
        if "enabled" in fields:
            credential.enabled = fields["enabled"]

        if any(section in fields for section in _SECTIONS):
            payload = self._decode(credential)
            for section in _SECTIONS:
                if section in fields and fields[section] is not None:
                    payload[section] = fields[section]
            credential.secret_ciphertext = encrypt(json.dumps(payload))

        self.session.flush()
        return self.to_read(credential)

    def delete(self, credential_id: int, user_id: int) -> None:
        self.repo.delete(self.get(credential_id, user_id))

    def secret_for_source(self, user_id: int, source_id: int) -> dict[str, dict[str, str]] | None:
        """Decrypted secret payload to inject for a user+source, or None."""
        credential = self.repo.for_source(user_id, source_id)
        if credential is None:
            return None
        return self._decode(credential)

    @staticmethod
    def _decode(credential: SiteCredential) -> dict[str, dict[str, str]]:
        raw = json.loads(decrypt(credential.secret_ciphertext))
        return {section: dict(raw.get(section) or {}) for section in _SECTIONS}

    def to_read(self, credential: SiteCredential) -> CredentialRead:
        payload = self._decode(credential)
        return CredentialRead(
            id=credential.id,
            source_id=credential.source_id,
            name=credential.name,
            enabled=credential.enabled,
            created_at=credential.created_at,
            has_cookies=bool(payload["cookies"]),
            has_headers=bool(payload["headers"]),
            has_session=bool(payload["session"]),
        )
