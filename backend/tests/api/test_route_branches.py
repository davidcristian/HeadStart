"""Branch coverage for small API-route conditionals."""

from __future__ import annotations

import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.appliers.types import ApplyResult
from app.core.config import settings
from app.notifiers.types import DeliveryResult
from app.scrapers.types import JobPosting
from app.services.apply import ApplyService
from app.services.pipeline import PipelineService
from app.services.targets import TargetService
from tests.conftest import register_and_login


def _seed_job(client: TestClient, headers: dict[str, str]) -> int:
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
        external_id="job-1",
        title="Engineer",
        company="ACME",
        location="Remote",
        url="https://acme.test/job-1",
    )
    with patch.object(PipelineService, "scrape", return_value=[posting]):
        client.post(f"/api/v1/searches/{search_id}/run", headers=headers)
    return client.get("/api/v1/jobs", headers=headers).json()[0]["id"]


def test_dry_run_submitted_result_includes_job(client: TestClient) -> None:
    """When a dry run reports 'submitted', the response echoes the current job row."""
    headers = register_and_login(client, "submitted-dry@example.com")
    job_id = _seed_job(client, headers)

    submitted = ApplyResult(status="submitted", payload={"ok": True})
    with patch.object(ApplyService, "apply_to_job", return_value=submitted):
        resp = client.post(
            f"/api/v1/jobs/{job_id}/apply",
            json={"dry_run": True},
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["job"] is not None
    assert body["job"]["id"] == job_id


def test_upload_empty_resume_is_rejected(client: TestClient) -> None:
    headers = register_and_login(client, "empty-resume@example.com")
    resp = client.put(
        "/api/v1/profile/resume",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_target_test_endpoint_sends_sample(client: TestClient) -> None:
    headers = register_and_login(client, "target-test@example.com")
    target_id = client.post(
        "/api/v1/targets",
        json={"name": "Phone", "type": "ntfy", "config": {"topic": "abc"}},
        headers=headers,
    ).json()["id"]

    sample = DeliveryResult(external_id="sample", status="sent")
    with patch.object(TargetService, "send_test", return_value=sample):
        resp = client.post(f"/api/v1/targets/{target_id}/test", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


def test_meta_hides_ads_when_ads_disabled(client: TestClient, monkeypatch) -> None:
    """With ads disabled the plan snapshot forces show_ads False."""
    monkeypatch.setattr(settings, "ads_enabled", False)
    headers = register_and_login(client, "ads-off@example.com")

    resp = client.get("/api/v1/meta", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["plan"]["show_ads"] is False
