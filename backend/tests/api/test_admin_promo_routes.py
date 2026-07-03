"""Route tests for the admin promo-code endpoints (list, update, redemptions)."""

from __future__ import annotations

import contextlib
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models.promo_code import PromoCode
from app.models.promo_redemption import PromoRedemption
from app.models.user import User
from app.repositories.promo_codes import PromoCodeRepository
from app.repositories.users import UserRepository
from tests.conftest import register_and_login


@contextmanager
def _client_db():
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    try:
        yield db
        db.commit()
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)


def _admin_headers(client: TestClient) -> dict[str, str]:
    # The first registered account becomes the bootstrap admin.
    return register_and_login(client, email="promo-admin@example.com", password="password123")


def test_admin_lists_promo_codes(client: TestClient) -> None:
    headers = _admin_headers(client)
    with _client_db() as db:
        PromoCodeRepository(db).add(
            PromoCode(code="LIST10", promo_type="percent_off", value_int=10)
        )

    resp = client.get("/api/v1/admin/promo-codes", headers=headers)
    assert resp.status_code == 200
    codes = {row["code"] for row in resp.json()}
    assert "LIST10" in codes


def test_admin_updates_promo_code(client: TestClient) -> None:
    headers = _admin_headers(client)
    with _client_db() as db:
        promo = PromoCodeRepository(db).add(
            PromoCode(code="UPD10", promo_type="percent_off", value_int=10, active=True)
        )
        promo_id = promo.id

    resp = client.patch(
        f"/api/v1/admin/promo-codes/{promo_id}",
        headers=headers,
        json={"active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False


def test_admin_lists_promo_redemptions(client: TestClient) -> None:
    headers = _admin_headers(client)
    with _client_db() as db:
        promo = PromoCodeRepository(db).add(
            PromoCode(code="RED10", promo_type="percent_off", value_int=10)
        )
        user = UserRepository(db).add(User(email="redeemer@example.com", password_hash="x"))
        PromoCodeRepository(db).add_redemption(
            PromoRedemption(promo_code_id=promo.id, user_id=user.id)
        )
        promo_id = promo.id

    resp = client.get(f"/api/v1/admin/promo-codes/{promo_id}/redemptions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
