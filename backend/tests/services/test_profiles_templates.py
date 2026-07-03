"""Unit tests for profile resume-template and validation behavior."""

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.application_profile import ApplicationProfile
from app.models.user import User
from app.schemas.profile import ProfileData
from app.services.profiles import ProfileService


def _user(session: Session, email: str = "u@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True)
    session.add(user)
    session.flush()
    return user.id


def _bundle_zip_bytes() -> bytes:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("main.tex", rb"\documentclass{article}\begin{document}Hi\end{document}")
        archive.writestr("section.tex", b"Section")
    return buf.getvalue()


def test_resume_template_upload_and_delete(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    tex = rb"\documentclass{article}\begin{document}Hi\end{document}"
    svc.save_resume_template(
        user_id,
        filename="resume.tex",
        content_type="application/x-tex",
        data=tex,
    )

    row = db_session.query(ApplicationProfile).filter_by(user_id=user_id).one()
    assert b"documentclass" not in row.data_ciphertext.encode()

    read = svc.get(user_id)
    assert read.resume_template is not None
    assert read.resume_template.filename == "resume.tex"
    assert svc.get_resume_template_tex(user_id) == tex.decode("utf-8")

    svc.delete_resume_template(user_id)
    assert svc.get(user_id).resume_template is None
    assert svc.get_resume_template_tex(user_id) is None


def test_resume_template_bundle_upload_and_round_trip(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    bundle = _bundle_zip_bytes()
    svc.save_resume_template(
        user_id,
        filename="resume.zip",
        content_type="application/zip",
        data=bundle,
    )

    read = svc.get(user_id)
    assert read.resume_template is not None
    assert read.resume_template.format == "bundle"
    assert read.resume_template.entrypoint == "main.tex"
    assert read.resume_template.file_count == 2
    assert svc.get_resume_template_tex(user_id) is None

    parsed = svc.get_resume_template_bundle(user_id)
    assert parsed is not None
    assert parsed.entrypoint == "main.tex"
    assert "section.tex" in parsed.files


def test_get_resume_template_tex_none_when_unset(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    # No profile at all.
    assert svc.get_resume_template_tex(user_id) is None
    # Profile with no template stored.
    svc.save(user_id, ProfileData(full_name="Ada"))
    assert svc.get_resume_template_tex(user_id) is None


def test_get_resume_template_tex_none_for_bundle_format(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    svc.save_resume_template(
        user_id, filename="resume.zip", content_type="application/zip", data=_bundle_zip_bytes()
    )
    # Bundle format has no single-file .tex source.
    assert svc.get_resume_template_tex(user_id) is None


def test_get_resume_template_bundle_none_when_unset(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    assert svc.get_resume_template_bundle(user_id) is None
    svc.save(user_id, ProfileData(full_name="Ada"))
    assert svc.get_resume_template_bundle(user_id) is None


def test_get_resume_template_bundle_none_for_single_format(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    svc.save_resume_template(
        user_id,
        filename="resume.tex",
        content_type="application/x-tex",
        data=rb"\documentclass{article}\begin{document}Hi\end{document}",
    )
    assert svc.get_resume_template_bundle(user_id) is None


def test_save_resume_template_replaces_existing_profile(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    svc.save(user_id, ProfileData(full_name="Ada"))
    read = svc.save_resume_template(
        user_id,
        filename="resume.tex",
        content_type="application/x-tex",
        data=rb"\documentclass{article}\begin{document}Hi\end{document}",
    )
    assert read.resume_template is not None
    assert read.full_name == "Ada"


def test_delete_resume_template_noop_without_profile(db_session: Session) -> None:
    user_id = _user(db_session)
    read = ProfileService(db_session).delete_resume_template(user_id)
    assert read.exists is False


def test_delete_resume_noop_without_profile(db_session: Session) -> None:
    user_id = _user(db_session)
    read = ProfileService(db_session).delete_resume(user_id)
    assert read.exists is False


def test_save_resume_rejects_blank_filename(db_session: Session) -> None:
    user_id = _user(db_session)
    with pytest.raises(ValidationError, match="filename is required"):
        ProfileService(db_session).save_resume(
            user_id, filename="   ", content_type="application/pdf", data=b"%PDF"
        )


def test_save_resume_rejects_bad_content_type(db_session: Session) -> None:
    user_id = _user(db_session)
    with pytest.raises(ValidationError, match="PDF or Word"):
        ProfileService(db_session).save_resume(
            user_id, filename="cv.txt", content_type="text/plain", data=b"hi"
        )


def test_save_resume_rejects_empty_file(db_session: Session) -> None:
    user_id = _user(db_session)
    with pytest.raises(ValidationError, match="empty"):
        ProfileService(db_session).save_resume(
            user_id, filename="cv.pdf", content_type="application/pdf", data=b""
        )


def test_save_resume_rejects_oversize_file(db_session: Session, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "profile_resume_max_bytes", 4)
    user_id = _user(db_session)
    with pytest.raises(ValidationError, match="exceeds"):
        ProfileService(db_session).save_resume(
            user_id, filename="cv.pdf", content_type="application/pdf", data=b"%PDF-too-big"
        )
