"""Direct unit tests for owned-entity repositories (targets, credentials, users)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.notification_target import NotificationTarget
from app.models.site_credential import SiteCredential
from app.models.source import Source
from app.models.user import User
from app.repositories.credentials import CredentialRepository
from app.repositories.targets import TargetRepository
from app.repositories.users import UserRepository


def _user(session: Session, email: str = "owned@example.test") -> User:
    return UserRepository(session).add(User(email=email, password_hash="x", is_active=True))


def test_target_delete(db_session: Session) -> None:
    user = _user(db_session)
    repo = TargetRepository(db_session)
    target = repo.add(
        NotificationTarget(user_id=user.id, name="t", type="ntfy", config={"topic": "x"})
    )

    repo.delete(target)
    db_session.flush()
    assert repo.list_all(user.id) == []


def test_credential_delete(db_session: Session) -> None:
    user = _user(db_session)
    source = Source(
        user_id=user.id, name="s", adapter_key="greenhouse", base_url="", default_config={}
    )
    db_session.add(source)
    db_session.flush()
    repo = CredentialRepository(db_session)
    cred = repo.add(SiteCredential(user_id=user.id, source_id=source.id, secret_ciphertext="x"))

    repo.delete(cred)
    db_session.flush()
    assert repo.list_all(user.id) == []


def test_get_by_stripe_customer_id(db_session: Session) -> None:
    user = _user(db_session)
    user.stripe_customer_id = "cus_abc"
    db_session.flush()
    repo = UserRepository(db_session)

    assert repo.get_by_stripe_customer_id("cus_abc").id == user.id
    assert repo.get_by_stripe_customer_id("cus_missing") is None
