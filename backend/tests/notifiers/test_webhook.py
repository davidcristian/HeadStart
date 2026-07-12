import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.webhook import WebhookNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
        posted_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_webhook_posts_expected_json_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert request.headers["content-type"] == "application/json"
        assert str(request.url) == "https://hooks.fixture.test/headstart"
        assert request.headers["host"] == "hooks.fixture.test"
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart"},
    )

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    body = captured[0]
    assert body["event"] == "job.new"
    assert body["job"] == {
        "external_id": "1",
        "title": "Software Engineer",
        "company": "Google",
        "location": "Amsterdam",
        "url": "https://careers.example/jobs/1",
        "summary": "",
        "posted_at": "2026-06-01T12:00:00+00:00",
    }


def test_webhook_includes_summary_when_present() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart"},
    )
    job = _job()
    job.summary = "Matches your search: mentions engineer."

    notifier.send(ctx, [job])

    assert captured[0]["job"]["summary"] == "Matches your search: mentions engineer."


def test_webhook_adds_hmac_signature_when_secret_configured() -> None:
    captured_headers: list[dict[str, str]] = []
    captured_body: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        captured_body.append(request.content)
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={
            "webhook_url": "https://hooks.fixture.test/headstart",
            "secret": "signing-key",
        },
    )

    notifier.send(ctx, [_job()])

    body = captured_body[0]
    expected = hmac.new(b"signing-key", body, hashlib.sha256).hexdigest()
    assert captured_headers[0]["x-headstart-signature"] == f"sha256={expected}"


def test_webhook_merges_custom_headers() -> None:
    captured_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={
            "webhook_url": "https://hooks.fixture.test/headstart",
            "headers": {"X-Custom": "value"},
        },
    )

    notifier.send(ctx, [_job()])

    assert captured_headers[0]["x-custom"] == "value"


def test_webhook_ignores_user_override_of_content_type_and_signature() -> None:
    """NTF-09: reserved Content-Type / signature headers always win over config."""
    captured_headers: list[dict[str, str]] = []
    captured_body: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        captured_body.append(request.content)
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={
            "webhook_url": "https://hooks.fixture.test/headstart",
            "secret": "signing-key",
            "headers": {
                "Content-Type": "text/plain",
                "content-type": "application/xml",
                "X-HeadStart-Signature": "sha256=forged",
                "x-headstart-signature": "sha256=also-forged",
                "X-Custom": "kept",
            },
        },
    )

    notifier.send(ctx, [_job()])

    headers = captured_headers[0]
    assert headers["content-type"] == "application/json"
    expected = hmac.new(b"signing-key", captured_body[0], hashlib.sha256).hexdigest()
    assert headers["x-headstart-signature"] == f"sha256={expected}"
    assert headers["x-custom"] == "kept"


def test_webhook_digest_posts_batched_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart"},
        digest=True,
        search_name="Backend roles",
    )

    results = notifier.send(ctx, [_job("1"), _job("2")])

    assert len(results) == 2
    assert all(r.status == "sent" for r in results)
    assert len(captured) == 1
    body = captured[0]
    assert body["event"] == "jobs.digest"
    assert body["search_name"] == "Backend roles"
    assert body["count"] == 2
    assert len(body["jobs"]) == 2


def test_webhook_records_failure_without_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart"},
    )

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


def test_webhook_requires_webhook_url() -> None:
    notifier = WebhookNotifier(client=httpx.Client())
    ctx = NotifyContext(target_type="webhook", config={})

    with pytest.raises(ValueError, match="webhook_url"):
        notifier.send(ctx, [_job()])


def test_webhook_rejects_unsafe_url() -> None:
    notifier = WebhookNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "http://127.0.0.1/hook"},
    )

    with pytest.raises(ValueError, match="not allowed"):
        notifier.send(ctx, [_job()])


def test_webhook_digest_empty_jobs_returns_empty() -> None:
    notifier = WebhookNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart"},
        digest=True,
    )
    assert notifier.send(ctx, []) == []


def test_webhook_digest_records_failure_without_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart"},
        digest=True,
    )
    results = notifier.send(ctx, [_job("1"), _job("2")])
    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


def test_webhook_skips_blank_custom_header_keys_and_values() -> None:
    captured_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={
            "webhook_url": "https://hooks.fixture.test/headstart",
            "headers": {"X-Keep": "yes", "": "no-key", "X-None": None},
        },
    )
    notifier.send(ctx, [_job()])
    headers = captured_headers[0]
    assert headers["x-keep"] == "yes"
    assert "x-none" not in headers


def test_webhook_ignores_non_dict_headers_config() -> None:
    captured_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        return httpx.Response(200, text="ok")

    notifier = WebhookNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="webhook",
        config={"webhook_url": "https://hooks.fixture.test/headstart", "headers": "nope"},
    )
    notifier.send(ctx, [_job()])
    assert captured_headers[0]["content-type"] == "application/json"


def test_webhook_close_behaviour() -> None:
    notifier = WebhookNotifier()
    notifier.close()
    assert notifier._client.is_closed

    client = httpx.Client()
    injected = WebhookNotifier(client=client)
    injected.close()
    assert not client.is_closed
    client.close()


def test_registry_resolves_webhook() -> None:
    assert isinstance(get_notifier("webhook"), WebhookNotifier)
