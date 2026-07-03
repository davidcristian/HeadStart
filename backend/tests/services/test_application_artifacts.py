"""Tests for application artifact persistence."""

import base64

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.services.application_artifacts import ApplicationArtifactService

FAKE_PDF = b"%PDF-1.4\nartifact test\n"


def test_store_tailored_resume_pdf_dedupes_by_hash(db_session: Session) -> None:
    service = ApplicationArtifactService(db_session)
    first = service.store_tailored_resume_pdf(
        1,
        data=FAKE_PDF,
        filename="resume-acme.pdf",
    )
    second = service.store_tailored_resume_pdf(
        1,
        data=FAKE_PDF,
        filename="resume-acme-copy.pdf",
    )
    assert first.id == second.id
    assert first.content_sha256 == second.content_sha256


def test_store_tailored_resume_pdf_rejects_non_pdf(db_session: Session) -> None:
    service = ApplicationArtifactService(db_session)
    with pytest.raises(ValidationError, match="PDF"):
        service.store_tailored_resume_pdf(1, data=b"not pdf", filename="bad.pdf")


def test_load_tailored_resume_pdf_round_trip(db_session: Session) -> None:
    service = ApplicationArtifactService(db_session)
    artifact = service.store_tailored_resume_pdf(
        1,
        data=FAKE_PDF,
        filename="resume-tailored.pdf",
    )
    resume = service.load_tailored_resume_pdf(1, artifact.id)
    assert resume.data == FAKE_PDF
    assert resume.filename == "resume-tailored.pdf"


def test_get_meta_scoped_to_owner(db_session: Session) -> None:
    service = ApplicationArtifactService(db_session)
    artifact = service.store_tailored_resume_pdf(
        1,
        data=FAKE_PDF,
        filename="resume-tailored.pdf",
    )
    meta = service.get_meta(1, artifact.id)
    assert meta.id == artifact.id
    assert meta.content_sha256 == artifact.content_sha256
    with pytest.raises(NotFoundError):
        service.get_meta(2, artifact.id)


def test_load_pdf_bytes_for_download(db_session: Session) -> None:
    service = ApplicationArtifactService(db_session)
    artifact = service.store_tailored_resume_pdf(
        1,
        data=FAKE_PDF,
        filename="resume-tailored.pdf",
    )
    data, filename, content_type = service.load_pdf_bytes(1, artifact.id)
    assert data == FAKE_PDF
    assert filename == "resume-tailored.pdf"
    assert content_type == "application/pdf"
    assert base64.b64encode(data).decode("ascii")
