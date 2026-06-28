"""Shared pytest fixtures.

Tests run against an in-memory SQLite database so they need no external services
and never touch the network.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.scrapers.http import HttpClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def register_and_login(
    client: TestClient, email: str = "user@example.com", password: str = "password123"
) -> dict[str, str]:
    """Register (idempotently) + log in, returning a Bearer auth header."""
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def load_json_fixture(name: str) -> object:
    return json.loads(load_fixture(name))


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A fresh in-memory database per test."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
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
    from app.main import app

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

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
