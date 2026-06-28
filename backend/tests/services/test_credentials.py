"""Unit tests for the encrypted site-credential service."""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.site_credential import SiteCredential
from app.models.source import Source
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialUpdate
from app.services.credentials import CredentialService


def _user_and_source(session: Session, email: str = "u@example.test") -> tuple[int, int]:
    user = User(email=email, password_hash="x", is_admin=False, is_active=True)
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
