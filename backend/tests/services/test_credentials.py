"""Unit tests for the encrypted site-credential service."""

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.site_credential import SiteCredential
from app.models.source import Source
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialUpdate
from app.services.credentials import CredentialService


def _user_and_source(session: Session, email: str = "u@example.test") -> tuple[int, int]:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True, plan="pro")
    session.add(user)
    session.flush()
    source = Source(user_id=user.id, name="src", adapter_key="greenhouse", default_config={})
    session.add(source)
    session.flush()
    return user.id, source.id


def test_create_encrypts_and_hides_secret(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)

    read = svc.create(
        user_id,
        CredentialCreate(
            source_id=source_id,
            name="login",
            enabled=True,
            cookies={"sessionid": "abc123"},
            headers={"X-Test": "1"},
        ),
    )
    # Read view never leaks secrets, only booleans.
    assert read.has_cookies is True
    assert read.has_headers is True
    assert read.has_session is False
    assert not hasattr(read, "cookies")

    # Stored ciphertext does not contain the plaintext cookie value.
    row = db_session.get(SiteCredential, read.id)
    assert row is not None
    assert "abc123" not in row.secret_ciphertext


def test_secret_for_source_round_trips(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)
    svc.create(
        user_id,
        CredentialCreate(source_id=source_id, cookies={"sessionid": "abc123"}),
    )

    secret = svc.secret_for_source(user_id, source_id)
    assert secret is not None
    assert secret["cookies"] == {"sessionid": "abc123"}


def test_disabled_credential_is_not_injected(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)
    read = svc.create(
        user_id,
        CredentialCreate(source_id=source_id, enabled=True, cookies={"k": "v"}),
    )
    svc.update(read.id, user_id, CredentialUpdate(enabled=False))
    assert svc.secret_for_source(user_id, source_id) is None


def test_list_all_and_get_read(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)
    created = svc.create(
        user_id,
        CredentialCreate(source_id=source_id, name="login", cookies={"k": "v"}),
    )

    listed = svc.list_all(user_id)
    assert len(listed) == 1
    assert listed[0].id == created.id

    read = svc.get_read(created.id, user_id)
    assert read.id == created.id
    assert read.name == "login"


def test_create_rejects_missing_source(db_session: Session) -> None:
    user = User(email="nosrc@example.test", password_hash="x", plan="pro")
    db_session.add(user)
    db_session.flush()
    svc = CredentialService(db_session)
    with pytest.raises(ValidationError, match="does not exist"):
        svc.create(user.id, CredentialCreate(source_id=999, cookies={"k": "v"}))


def test_update_name_enabled_and_sections(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)
    created = svc.create(
        user_id,
        CredentialCreate(source_id=source_id, name="old", enabled=True, cookies={"a": "1"}),
    )

    updated = svc.update(
        created.id,
        user_id,
        CredentialUpdate(
            name="new",
            enabled=False,
            headers={"X-Token": "abc"},
            session=None,
        ),
    )

    assert updated.name == "new"
    assert updated.enabled is False
    assert updated.has_headers is True
    # Unspecified section stays intact; explicit None is ignored.
    assert updated.has_cookies is True
    assert updated.has_session is False


def test_update_name_only_leaves_enabled_untouched(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)
    created = svc.create(
        user_id,
        CredentialCreate(source_id=source_id, name="old", enabled=True, cookies={"a": "1"}),
    )

    updated = svc.update(created.id, user_id, CredentialUpdate(name="renamed"))

    assert updated.name == "renamed"
    assert updated.enabled is True
    assert updated.has_cookies is True


def test_delete_removes_credential(db_session: Session) -> None:
    user_id, source_id = _user_and_source(db_session)
    svc = CredentialService(db_session)
    created = svc.create(user_id, CredentialCreate(source_id=source_id, cookies={"k": "v"}))

    svc.delete(created.id, user_id)
    db_session.flush()

    with pytest.raises(NotFoundError):
        svc.get(created.id, user_id)


def test_cross_user_access_is_denied(db_session: Session) -> None:
    owner_id, source_id = _user_and_source(db_session, "owner@example.test")
    other = User(email="other@example.test", password_hash="x")
    db_session.add(other)
    db_session.flush()

    svc = CredentialService(db_session)
    read = svc.create(owner_id, CredentialCreate(source_id=source_id, cookies={"k": "v"}))

    try:
        svc.get(read.id, other.id)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass
    assert svc.secret_for_source(other.id, source_id) is None
