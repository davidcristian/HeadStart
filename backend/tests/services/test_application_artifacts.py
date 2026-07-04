"""Tests for application artifact persistence."""

import base64

import pytest
from sqlalchemy.orm import Session

from app.core.crypto import encrypt
from app.core.exceptions import NotFoundError, ValidationError
from app.models.application_artifact import ApplicationArtifact
from app.models.user import User
from app.services.application_artifacts import ApplicationArtifactService

FAKE_PDF = b"%PDF-1.4\nartifact test\n"


def test_store_tailored_resume_pdf_dedupes_by_hash(
    db_session: Session, default_test_user: User
) -> None:
    service = ApplicationArtifactService(db_session)
    first = service.store_tailored_resume_pdf(
        default_test_user.id,
        data=FAKE_PDF,
        filename="resume-acme.pdf",
    )
    second = service.store_tailored_resume_pdf(
        default_test_user.id,
        data=FAKE_PDF,
        filename="resume-acme-copy.pdf",
    )
    assert first.id == second.id
    assert first.content_sha256 == second.content_sha256


def test_store_tailored_resume_pdf_rejects_non_pdf(
    db_session: Session, default_test_user: User
) -> None:
    service = ApplicationArtifactService(db_session)
    with pytest.raises(ValidationError, match="PDF"):
        service.store_tailored_resume_pdf(default_test_user.id, data=b"not pdf", filename="bad.pdf")


def test_store_tailored_resume_pdf_rejects_empty(
    db_session: Session, default_test_user: User
) -> None:
    service = ApplicationArtifactService(db_session)
    with pytest.raises(ValidationError, match="empty"):
        service.store_tailored_resume_pdf(default_test_user.id, data=b"", filename="empty.pdf")


def _store_foreign_artifact(session: Session, user_id: int) -> int:
    artifact = ApplicationArtifact(
        user_id=user_id,
        artifact_type="other_type",
        content_sha256="deadbeef",
        filename="other.pdf",
        content_type="application/pdf",
        size_bytes=len(FAKE_PDF),
        data_ciphertext=encrypt(base64.b64encode(FAKE_PDF).decode("ascii")),
    )
    session.add(artifact)
    session.flush()
    return artifact.id


def test_load_tailored_resume_pdf_rejects_wrong_type(
    db_session: Session, default_test_user: User
) -> None:
    artifact_id = _store_foreign_artifact(db_session, default_test_user.id)
    service = ApplicationArtifactService(db_session)
    with pytest.raises(ValidationError, match="not a tailored resume"):
        service.load_tailored_resume_pdf(default_test_user.id, artifact_id)


def test_load_pdf_bytes_rejects_wrong_type(db_session: Session, default_test_user: User) -> None:
    artifact_id = _store_foreign_artifact(db_session, default_test_user.id)
    service = ApplicationArtifactService(db_session)
    with pytest.raises(ValidationError, match="not a tailored resume"):
        service.load_pdf_bytes(default_test_user.id, artifact_id)


def test_load_tailored_resume_pdf_round_trip(db_session: Session, default_test_user: User) -> None:
    service = ApplicationArtifactService(db_session)
    artifact = service.store_tailored_resume_pdf(
        default_test_user.id,
        data=FAKE_PDF,
        filename="resume-tailored.pdf",
    )
    resume = service.load_tailored_resume_pdf(default_test_user.id, artifact.id)
    assert resume.data == FAKE_PDF
    assert resume.filename == "resume-tailored.pdf"


def test_get_meta_scoped_to_owner(db_session: Session, default_test_user: User) -> None:
    other = User(email="other-artifact@example.com", password_hash="hash")
    db_session.add(other)
    db_session.flush()
    service = ApplicationArtifactService(db_session)
    artifact = service.store_tailored_resume_pdf(
        default_test_user.id,
        data=FAKE_PDF,
        filename="resume-tailored.pdf",
    )
    meta = service.get_meta(default_test_user.id, artifact.id)
    assert meta.id == artifact.id
    assert meta.content_sha256 == artifact.content_sha256
    with pytest.raises(NotFoundError):
        service.get_meta(other.id, artifact.id)


def test_load_pdf_bytes_for_download(db_session: Session, default_test_user: User) -> None:
    service = ApplicationArtifactService(db_session)
    artifact = service.store_tailored_resume_pdf(
        default_test_user.id,
        data=FAKE_PDF,
        filename="resume-tailored.pdf",
    )
    data, filename, content_type = service.load_pdf_bytes(default_test_user.id, artifact.id)
    assert data == FAKE_PDF
    assert filename == "resume-tailored.pdf"
    assert content_type == "application/pdf"
    assert base64.b64encode(data).decode("ascii")
