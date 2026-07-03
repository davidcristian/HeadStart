"""Tests for tailored resume decoding."""

import base64

import pytest

from app.core.exceptions import ValidationError
from app.services.tailored_resume import decode_tailored_resume

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
