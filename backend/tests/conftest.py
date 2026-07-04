"""Shared pytest fixtures.

Tests run against an in-memory SQLite database so they need no external services
and never touch the network.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.registration_lock import RegistrationLock
from app.models.user import User
from app.scrapers.http import HttpClient


def seed_registration_lock(session: Session) -> None:
    """Tests use create_all instead of migrations; seed the registration lock row."""
    if session.get(RegistrationLock, 1) is None:
        session.add(RegistrationLock(id=1))
        session.flush()


def seed_default_test_user(session: Session) -> User:
    """Many unit tests reference user_id=1; seed a row so FK constraints hold."""
    existing = session.get(User, 1)
    if existing is not None:
        return existing
    user = User(id=1, email="test-user@example.com", password_hash="hash", plan="free")
    session.add(user)
    session.flush()
    return user


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def register_and_login(
    client: TestClient, email: str = "user@example.com", password: str = "password123"
) -> dict[str, str]:
    """Register (idempotently) + verify email + log in, returning a Bearer auth header."""
    with (
        patch("app.services.auth.send_verification_email"),
        patch("app.services.auth.generate_password_reset_token", return_value="test-verify-token"),
    ):
        client.post("/api/v1/auth/register", json={"email": email, "password": password})
    client.post("/api/v1/auth/verify-email", json={"token": "test-verify-token"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def load_json_fixture(name: str) -> object:
    return json.loads(load_fixture(name))


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """SQLite disables FK enforcement by default; match Postgres cascade semantics in tests."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture
def default_test_user(db_session: Session) -> User:
    """Opt-in row for tests that reference user_id=1 without creating a user."""
    return seed_default_test_user(db_session)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A fresh in-memory database per test."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    seed_registration_lock(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def make_http_client(handler: "callable[[httpx.Request], httpx.Response]") -> HttpClient:
    """Build an HttpClient backed by a mock transport (no real network)."""
    transport = httpx.MockTransport(handler)
    return HttpClient(client=httpx.Client(transport=transport, follow_redirects=True))


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A FastAPI TestClient wired to a shared in-memory SQLite database."""
    from app.api.deps import get_db
    from app.core.config import settings
    from app.main import app

    # The TestClient talks plain HTTP, so allow the refresh cookie to flow
    # without the Secure flag (it defaults to Secure for real deployments).
    settings.auth_cookie_secure = False

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as bootstrap:
        seed_registration_lock(bootstrap)
        bootstrap.commit()

    def override_get_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Bearer header for a freshly-registered default user."""
    return register_and_login(client)
