"""Route tests for async search runs."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.pipeline import PipelineService, RunResult
from app.worker.tasks import run_search_run_task
from tests.conftest import post_search_run, register_and_login


def _create_search(client: TestClient, headers: dict[str, str]) -> int:
    source_id = client.post(
        "/api/v1/sources",
        json={"name": "ACME", "adapter_key": "greenhouse"},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/searches",
        json={"name": "ACME SWE", "source_id": source_id, "interval_seconds": 60},
        headers=headers,
    ).json()["id"]


def test_run_search_queues(client: TestClient) -> None:
    headers = register_and_login(client, "search-run-queue@example.com")
    search_id = _create_search(client, headers)

    with patch.object(run_search_run_task, "delay") as mock_delay:
        resp = client.post(f"/api/v1/searches/{search_id}/run", headers=headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["search_id"] == search_id
    assert body["found"] == 0
    run_id = body["id"]
    mock_delay.assert_called_once_with(run_id, mock_delay.call_args[0][1], search_id)

    polled = client.get(f"/api/v1/search-runs/{run_id}", headers=headers)
    assert polled.status_code == 200
    assert polled.json()["status"] == "queued"


def test_run_search_inline_completes_with_counts(client: TestClient) -> None:
    headers = register_and_login(client, "search-run-complete@example.com")
    search_id = _create_search(client, headers)
    expected = RunResult(search_id=search_id, found=3, new=2, notified=1, filtered=1)

    with patch.object(PipelineService, "run", return_value=expected):
        resp = post_search_run(client, search_id, headers)

    assert resp.status_code == 202
    run_id = resp.json()["id"]
    polled = client.get(f"/api/v1/search-runs/{run_id}", headers=headers)
    assert polled.status_code == 200
    body = polled.json()
    assert body["status"] == "ready"
    assert body["found"] == 3
    assert body["new"] == 2
    assert body["notified"] == 1
    assert body["filtered"] == 1


def test_search_run_isolation(client: TestClient) -> None:
    alice = register_and_login(client, "search-run-alice@example.com")
    bob = register_and_login(client, "search-run-bob@example.com")
    search_id = _create_search(client, alice)
    with patch.object(run_search_run_task, "delay"):
        run_id = client.post(f"/api/v1/searches/{search_id}/run", headers=alice).json()["id"]
    assert client.get(f"/api/v1/search-runs/{run_id}", headers=bob).status_code == 404
