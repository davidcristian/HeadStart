"""Tests for schema validators and helper methods lacking coverage."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from app.schemas.inbox_classification import EmailClassifyRequest
from app.schemas.inbox_reply_draft import ReplyDraftRequest
from app.schemas.profile import ProfileData, ResumeTemplateStored

# ---- inbox_reply_draft ----


def test_reply_draft_request_requires_classification_or_uid() -> None:
    with pytest.raises(ValidationError, match="Provide either classification_id or message_uid"):
        ReplyDraftRequest()


def test_reply_draft_request_accepts_classification_id() -> None:
    assert ReplyDraftRequest(classification_id=1).classification_id == 1


# ---- inbox_classification ----


def test_classify_request_requires_message_or_uid() -> None:
    with pytest.raises(ValidationError, match="Provide either message or uid"):
        EmailClassifyRequest()


def test_classify_request_accepts_uid() -> None:
    assert EmailClassifyRequest(uid=5).uid == 5


# ---- profile: skills validator ----


def test_profile_rejects_too_many_skills() -> None:
    with pytest.raises(ValidationError, match="cannot exceed 100 entries"):
        ProfileData(skills=[f"skill{i}" for i in range(101)])


def test_profile_rejects_overlong_skill_name() -> None:
    with pytest.raises(ValidationError, match="cannot exceed 200 characters"):
        ProfileData(skills=["x" * 201])


def test_profile_accepts_valid_skills() -> None:
    assert ProfileData(skills=["python", "sql"]).skills == ["python", "sql"]


# ---- profile: answers validator (API-13) ----


def test_profile_rejects_too_many_answers() -> None:
    with pytest.raises(ValidationError, match="answers cannot exceed 100 entries"):
        ProfileData(answers={f"q{i}": "yes" for i in range(101)})


def test_profile_rejects_overlong_answers_key() -> None:
    with pytest.raises(ValidationError, match="each answers key cannot exceed 200 characters"):
        ProfileData(answers={"k" * 201: "yes"})


def test_profile_rejects_overlong_answers_value() -> None:
    with pytest.raises(ValidationError, match="each answers value cannot exceed 200 characters"):
        ProfileData(answers={"work_authorization": "x" * 201})


def test_profile_accepts_valid_answers() -> None:
    answers = {"work_authorization": "UK citizen", "notice_period": "2 weeks"}
    assert ProfileData(answers=answers).answers == answers


# ---- profile: ResumeTemplateStored helpers ----


def test_resume_template_from_bytes_is_single_tex() -> None:
    stored = ResumeTemplateStored.from_bytes(filename="cv.tex", data=b"\\documentclass{article}")
    assert stored.format == "single"
    assert stored.decode_tex() == "\\documentclass{article}"


def test_decode_tex_rejects_bundle() -> None:
    bundle = ResumeTemplateStored.from_bundle_zip(
        filename="cv.zip",
        data=b"PK\x03\x04",
        entrypoint="main.tex",
        file_count=2,
    )
    with pytest.raises(ValueError, match="only valid for single-file templates"):
        bundle.decode_tex()


def test_decode_bundle_zip_rejects_single() -> None:
    single = ResumeTemplateStored.from_single_tex(filename="cv.tex", data=b"body")
    with pytest.raises(ValueError, match="only valid for bundle templates"):
        single.decode_bundle_zip()


def test_decode_bundle_zip_round_trip() -> None:
    raw = b"PK-bundle-bytes"
    bundle = ResumeTemplateStored.from_bundle_zip(
        filename="cv.zip", data=raw, entrypoint="main.tex", file_count=1
    )
    assert bundle.decode_bundle_zip() == raw
    assert base64.b64decode(bundle.data_b64) == raw
