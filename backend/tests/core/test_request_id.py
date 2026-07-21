"""Tests for request/task correlation ids in logs."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.logging import (
    RequestIdFilter,
    get_request_id,
    reset_request_id,
    set_request_id,
)
from app.core.request_id import (
    REQUEST_ID_HEADER,
    bind_celery_task_id,
    resolve_request_id,
)
from app.worker import celery_app as celery_module


def test_request_id_filter_injects_active_id() -> None:
    set_request_id("req-abc")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert RequestIdFilter().filter(record) is True
        assert record.__dict__["request_id"] == "req-abc"
    finally:
        reset_request_id()


def test_request_id_defaults_to_dash() -> None:
    reset_request_id()
    assert get_request_id() == "-"


def test_resolve_request_id_accepts_well_formed_client_value() -> None:
    assert resolve_request_id("abc-123_XYZ.9") == "abc-123_XYZ.9"


def test_resolve_request_id_rejects_unsafe_or_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.request_id.uuid.uuid4", lambda: "minted-id")
    assert resolve_request_id(None) == "minted-id"
    assert resolve_request_id("") == "minted-id"
    assert resolve_request_id("   ") == "minted-id"
    assert resolve_request_id("bad id with spaces") == "minted-id"
    assert resolve_request_id("has\nnewline") == "minted-id"
    assert resolve_request_id("x" * 129) == "minted-id"


def test_health_echoes_generated_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    echoed = response.headers.get(REQUEST_ID_HEADER)
    assert echoed is not None
    assert resolve_request_id(echoed) == echoed


def test_health_honors_client_request_id(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health",
        headers={REQUEST_ID_HEADER: "client-corr-42"},
    )
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER) == "client-corr-42"


def test_middleware_binds_id_during_request(client: TestClient) -> None:
    seen: list[str] = []

    @client.app.get("/_test_request_id", include_in_schema=False)
    def _probe() -> dict[str, str]:
        seen.append(get_request_id())
        return {"ok": "1"}

    response = client.get(
        "/_test_request_id",
        headers={REQUEST_ID_HEADER: "during-request"},
    )
    assert response.status_code == 200
    assert seen == ["during-request"]
    assert get_request_id() == "-"


def test_bind_celery_task_id_sets_and_clears() -> None:
    bind_celery_task_id("celery-task-1")
    assert get_request_id() == "celery-task-1"
    bind_celery_task_id(None)
    assert get_request_id() == "-"
    reset_request_id()


def test_celery_prerun_and_postrun_handlers() -> None:
    with patch.object(celery_module, "bind_celery_task_id") as mock_bind:
        celery_module._bind_task_request_id(task_id="tid-9")
    mock_bind.assert_called_once_with("tid-9")

    with patch.object(celery_module, "reset_request_id") as mock_reset:
        celery_module._clear_task_request_id()
    mock_reset.assert_called_once_with()
