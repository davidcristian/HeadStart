"""Tests for tailored resume decoding."""

import base64

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.user import User
from app.services.application_artifacts import ApplicationArtifactService
from app.services.tailored_resume import (
    decode_tailored_resume,
    resolve_tailored_resume_for_apply,
)

FAKE_PDF = b"%PDF-1.4\nfake resume\n"


def test_decode_tailored_resume_accepts_valid_pdf() -> None:
    resume = decode_tailored_resume(base64.b64encode(FAKE_PDF).decode("ascii"))
    assert resume is not None
    assert resume.content_type == "application/pdf"
    assert resume.data == FAKE_PDF


def test_decode_tailored_resume_rejects_non_pdf() -> None:
    with pytest.raises(ValidationError, match="PDF"):
        decode_tailored_resume(base64.b64encode(b"not a pdf").decode("ascii"))


def test_decode_tailored_resume_none_for_empty() -> None:
    assert decode_tailored_resume(None) is None
    assert decode_tailored_resume("") is None
    assert decode_tailored_resume("   ") is None


def test_decode_tailored_resume_rejects_invalid_base64() -> None:
    with pytest.raises(ValidationError, match="valid base64"):
        decode_tailored_resume("!!!not base64!!!")


def test_decode_tailored_resume_rejects_oversized(monkeypatch) -> None:
    monkeypatch.setattr(settings, "profile_resume_max_bytes", 4)
    with pytest.raises(ValidationError, match="MB limit"):
        decode_tailored_resume(base64.b64encode(FAKE_PDF).decode("ascii"))


def test_resolve_tailored_resume_none_when_no_input(
    db_session: Session, default_test_user: User
) -> None:
    resume, artifact_id = resolve_tailored_resume_for_apply(
        db_session,
        default_test_user.id,
        tailored_resume_b64=None,
        tailored_resume_artifact_id=None,
    )
    assert resume is None
    assert artifact_id is None


def test_resolve_tailored_resume_loads_existing_artifact(
    db_session: Session, default_test_user: User
) -> None:
    artifact = ApplicationArtifactService(db_session).store_tailored_resume_pdf(
        default_test_user.id, data=FAKE_PDF, filename="resume.pdf"
    )
    resume, artifact_id = resolve_tailored_resume_for_apply(
        db_session,
        default_test_user.id,
        tailored_resume_b64=None,
        tailored_resume_artifact_id=artifact.id,
    )
    assert resume is not None
    assert resume.data == FAKE_PDF
    assert artifact_id == artifact.id


def test_resolve_tailored_resume_stores_new_from_b64(
    db_session: Session, default_test_user: User
) -> None:
    resume, artifact_id = resolve_tailored_resume_for_apply(
        db_session,
        default_test_user.id,
        tailored_resume_b64=base64.b64encode(FAKE_PDF).decode("ascii"),
        tailored_resume_artifact_id=None,
    )
    assert resume is not None
    assert resume.data == FAKE_PDF
    assert artifact_id is not None
    loaded = ApplicationArtifactService(db_session).load_tailored_resume_pdf(
        default_test_user.id, artifact_id
    )
    assert loaded.data == FAKE_PDF
