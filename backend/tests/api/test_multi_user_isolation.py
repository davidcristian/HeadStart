"""Cross-user isolation: one user's owned entities are invisible to another.

Owned entities carry a `user_id` and every route scopes to `get_current_user`
(AGENTS.md §1). These tests pin that a second user can neither list nor
fetch/patch/delete another user's sources, searches, targets, credentials,
jobs, or applications.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scrapers.types import JobPosting
from app.services.pipeline import PipelineService
from tests.conftest import post_search_run, register_and_login


def _seed_job(client: TestClient, headers: dict[str, str], *, external_id: str = "iso-job") -> int:
    """Create a source + search and scrape one posting, returning its job id."""
    source_id = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse"},
        headers=headers,
    ).json()["id"]
    search_id = client.post(
        "/api/v1/searches",
        json={"name": "ACME SWE", "source_id": source_id, "interval_seconds": 60},
        headers=headers,
    ).json()["id"]
    posting = JobPosting(
        external_id=external_id,
        title="Platform Engineer",
        company="Globex",
        location="Berlin",
        url=f"https://boards.greenhouse.io/acme/jobs/{external_id}",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        post_search_run(client, search_id, headers)
    return client.get("/api/v1/jobs", headers=headers).json()[0]["id"]


def test_users_cannot_see_each_others_sources(client: TestClient) -> None:
    alice = register_and_login(client, "alice@example.com")
    bob = register_and_login(client, "bob@example.com")

    source_id = client.post(
        "/api/v1/sources",
        json={"name": "Alice Co", "adapter_key": "greenhouse"},
        headers=alice,
    ).json()["id"]

    # Alice sees it; Bob does not.
    assert len(client.get("/api/v1/sources", headers=alice).json()) == 1
    assert client.get("/api/v1/sources", headers=bob).json() == []

    # Bob cannot fetch, patch, or delete Alice's source.
    assert client.get(f"/api/v1/sources/{source_id}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/sources/{source_id}", json={"enabled": False}, headers=bob
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/sources/{source_id}", headers=bob).status_code == 404


def test_users_cannot_see_each_others_searches(client: TestClient) -> None:
    alice = register_and_login(client, "alice-s@example.com")
    bob = register_and_login(client, "bob-s@example.com")

    source_id = client.post(
        "/api/v1/sources", json={"name": "Alice Co", "adapter_key": "greenhouse"}, headers=alice
    ).json()["id"]
    search_id = client.post(
        "/api/v1/searches",
        json={"name": "Alice Search", "source_id": source_id, "interval_seconds": 60},
        headers=alice,
    ).json()["id"]

    assert len(client.get("/api/v1/searches", headers=alice).json()) == 1
    assert client.get("/api/v1/searches", headers=bob).json() == []

    assert client.get(f"/api/v1/searches/{search_id}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/searches/{search_id}", json={"name": "hijack"}, headers=bob
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/searches/{search_id}", headers=bob).status_code == 404


def test_users_cannot_see_each_others_targets(client: TestClient) -> None:
    alice = register_and_login(client, "alice-t@example.com")
    bob = register_and_login(client, "bob-t@example.com")

    target_id = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "jobs-a1b2c3d4e5f67890"}},
        headers=alice,
    ).json()["id"]

    assert len(client.get("/api/v1/targets", headers=alice).json()) == 1
    assert client.get("/api/v1/targets", headers=bob).json() == []

    assert client.get(f"/api/v1/targets/{target_id}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/targets/{target_id}", json={"name": "hijack"}, headers=bob
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/targets/{target_id}", headers=bob).status_code == 404


def test_users_cannot_see_each_others_credentials(client: TestClient) -> None:
    alice = register_and_login(client, "alice-c@example.com")
    bob = register_and_login(client, "bob-c@example.com")

    alice_source = client.post(
        "/api/v1/sources", json={"name": "Alice Co", "adapter_key": "greenhouse"}, headers=alice
    ).json()["id"]
    credential_id = client.post(
        "/api/v1/credentials",
        json={"source_id": alice_source, "name": "creds", "cookies": {"sessionid": "abc123"}},
        headers=alice,
    ).json()["id"]

    assert len(client.get("/api/v1/credentials", headers=alice).json()) == 1
    assert client.get("/api/v1/credentials", headers=bob).json() == []

    assert client.get(f"/api/v1/credentials/{credential_id}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/credentials/{credential_id}", json={"name": "hijack"}, headers=bob
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/credentials/{credential_id}", headers=bob).status_code == 404


def test_users_cannot_see_each_others_jobs(client: TestClient) -> None:
    alice = register_and_login(client, "alice-j@example.com")
    bob = register_and_login(client, "bob-j@example.com")

    alice_job = _seed_job(client, alice, external_id="alice-job")

    assert len(client.get("/api/v1/jobs", headers=alice).json()) == 1
    assert client.get("/api/v1/jobs", headers=bob).json() == []

    assert (
        client.patch(
            f"/api/v1/jobs/{alice_job}", json={"status": "applied"}, headers=bob
        ).status_code
        == 404
    )


def test_users_cannot_see_each_others_applications(client: TestClient) -> None:
    alice = register_and_login(client, "alice-a@example.com")
    bob = register_and_login(client, "bob-a@example.com")

    alice_job = _seed_job(client, alice, external_id="alice-app-job")
    client.patch(f"/api/v1/jobs/{alice_job}", json={"status": "applied"}, headers=alice)

    assert len(client.get("/api/v1/applications", headers=alice).json()) == 1
    assert client.get("/api/v1/applications", headers=bob).json() == []
