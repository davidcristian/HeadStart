"""Unit tests for the encrypted application-profile service."""

from sqlalchemy.orm import Session

from app.models.application_profile import ApplicationProfile
from app.models.user import User
from app.schemas.profile import ProfileData, ProfileLinks
from app.services.profiles import ProfileService


def _user(session: Session, email: str = "u@example.test") -> int:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True)
    session.add(user)
    session.flush()
    return user.id


def test_get_returns_empty_defaults_when_unset(db_session: Session) -> None:
    user_id = _user(db_session)
    read = ProfileService(db_session).get(user_id)
    assert read.exists is False
    assert read.full_name == ""
    assert read.answers == {}
    assert read.updated_at is None


def test_save_round_trips_and_marks_exists(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)

    read = svc.save(
        user_id,
        ProfileData(
            full_name="Ada Lovelace",
            email="ada@example.test",
            phone="+1 555 0100",
            location="London",
            links=ProfileLinks(github="https://github.com/ada"),
            resume_text="Pioneering programmer.",
            cover_letter_template="Dear {company}, ...",
            answers={"work_authorization": "UK citizen"},
        ),
    )
    assert read.exists is True
    assert read.full_name == "Ada Lovelace"
    assert read.updated_at is not None

    fetched = svc.get(user_id)
    assert fetched.exists is True
    assert fetched.email == "ada@example.test"
    assert fetched.links.github == "https://github.com/ada"
    assert fetched.resume_text == "Pioneering programmer."
    assert fetched.answers == {"work_authorization": "UK citizen"}


def test_payload_is_encrypted_at_rest(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    read = svc.save(user_id, ProfileData(full_name="Ada Lovelace", resume_text="secret-resume"))
    assert read.exists is True

    row = db_session.query(ApplicationProfile).filter_by(user_id=user_id).one()
    assert "secret-resume" not in row.data_ciphertext
    assert "Ada Lovelace" not in row.data_ciphertext


def test_save_twice_replaces_profile(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    svc.save(user_id, ProfileData(full_name="First", answers={"a": "1"}))
    svc.save(user_id, ProfileData(full_name="Second"))

    fetched = svc.get(user_id)
    assert fetched.full_name == "Second"
    # PUT is a full replacement, so the old answer is gone.
    assert fetched.answers == {}
    # Exactly one row exists per user.
    rows = db_session.query(ApplicationProfile).filter_by(user_id=user_id).all()
    assert len(rows) == 1


def test_delete_is_idempotent(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    svc.save(user_id, ProfileData(full_name="Ada"))

    svc.delete(user_id)
    assert svc.get(user_id).exists is False
    # Deleting again does not raise.
    svc.delete(user_id)


def test_profiles_are_isolated_per_user(db_session: Session) -> None:
    owner_id = _user(db_session, "owner@example.test")
    other_id = _user(db_session, "other@example.test")
    svc = ProfileService(db_session)

    svc.save(owner_id, ProfileData(full_name="Owner"))
    assert svc.get(other_id).exists is False
    assert svc.get(owner_id).full_name == "Owner"


def test_resume_upload_persists_encrypted_and_survives_profile_save(db_session: Session) -> None:
    user_id = _user(db_session)
    svc = ProfileService(db_session)
    svc.save(user_id, ProfileData(full_name="Ada", email="ada@example.test"))
    svc.save_resume(
        user_id,
        filename="resume.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.4",
    )

    row = db_session.query(ApplicationProfile).filter_by(user_id=user_id).one()
    assert "%PDF-1.4" not in row.data_ciphertext

    read = svc.get(user_id)
    assert read.resume_file is not None
    assert read.resume_file.filename == "resume.pdf"

    apply_profile = svc.get_for_apply(user_id)
    assert apply_profile.resume_file is not None
    assert apply_profile.resume_file.data == b"%PDF-1.4"

    svc.save(user_id, ProfileData(full_name="Ada Updated", email="ada@example.test"))
    after_save = svc.get(user_id)
    assert after_save.full_name == "Ada Updated"
    assert after_save.resume_file is not None
    assert after_save.resume_file.filename == "resume.pdf"

    svc.delete_resume(user_id)
    assert svc.get(user_id).resume_file is None
