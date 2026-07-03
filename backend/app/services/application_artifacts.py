"""Persist and retrieve generated application documents."""

from __future__ import annotations

import base64
import hashlib

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.core.exceptions import NotFoundError, ValidationError
from app.models.application_artifact import ApplicationArtifact
from app.repositories.application_artifacts import ApplicationArtifactRepository
from app.schemas.application_artifact import ApplicationArtifactMeta
from app.schemas.profile import ResumeFile

TAILORED_RESUME_PDF = "tailored_resume_pdf"


class ApplicationArtifactService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ApplicationArtifactRepository(session)

    def store_tailored_resume_pdf(
        self,
        user_id: int,
        *,
        data: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> ApplicationArtifact:
        """Persist a tailored resume PDF, deduplicating by per-user content hash."""
        if not data.startswith(b"%PDF"):
            raise ValidationError("Artifact must be a PDF")
        if len(data) == 0:
            raise ValidationError("Artifact PDF is empty")

        digest = hashlib.sha256(data).hexdigest()
        existing = self.repo.get_by_hash(user_id, digest)
        if existing is not None:
            return existing

        artifact = self.repo.add(
            ApplicationArtifact(
                user_id=user_id,
                artifact_type=TAILORED_RESUME_PDF,
                content_sha256=digest,
                filename=filename,
                content_type=content_type,
                size_bytes=len(data),
                data_ciphertext=self._encrypt_bytes(data),
            )
        )
        return artifact

    def get_meta(self, user_id: int, artifact_id: int) -> ApplicationArtifactMeta:
        """Return artifact metadata for the authenticated owner."""
        artifact = self._require_owned(user_id, artifact_id)
        return ApplicationArtifactMeta.model_validate(artifact)

    def load_tailored_resume_pdf(self, user_id: int, artifact_id: int) -> ResumeFile:
        """Decrypt and return a stored tailored resume as a ResumeFile."""
        artifact = self._require_owned(user_id, artifact_id)
        if artifact.artifact_type != TAILORED_RESUME_PDF:
            raise ValidationError("Artifact is not a tailored resume PDF")
        data = self._decrypt_bytes(artifact.data_ciphertext)
        return ResumeFile(
            filename=artifact.filename,
            content_type=artifact.content_type,
            size_bytes=artifact.size_bytes,
            data=data,
        )

    def load_pdf_bytes(self, user_id: int, artifact_id: int) -> tuple[bytes, str, str]:
        """Return raw PDF bytes, filename, and content type for download."""
        artifact = self._require_owned(user_id, artifact_id)
        if artifact.artifact_type != TAILORED_RESUME_PDF:
            raise ValidationError("Artifact is not a tailored resume PDF")
        data = self._decrypt_bytes(artifact.data_ciphertext)
        return data, artifact.filename, artifact.content_type

    def _require_owned(self, user_id: int, artifact_id: int) -> ApplicationArtifact:
        artifact = self.repo.get_for_user(artifact_id, user_id)
        if artifact is None:
            raise NotFoundError(f"Application artifact {artifact_id} not found")
        return artifact

    @staticmethod
    def _encrypt_bytes(data: bytes) -> str:
        return encrypt(base64.b64encode(data).decode("ascii"))

    @staticmethod
    def _decrypt_bytes(ciphertext: str) -> bytes:
        return base64.b64decode(decrypt(ciphertext))
