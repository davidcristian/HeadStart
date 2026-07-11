import httpx
import pytest

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.ntfy import NtfyNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
    )


def test_ntfy_posts_expected_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        assert str(request.url) == "https://ntfy.fixture.test"
        assert request.headers["host"] == "ntfy.fixture.test"
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="ntfy",
        config={"topic": "secret", "priority": "high", "server_url": "https://ntfy.fixture.test"},
    )

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    body = captured[0]
    assert body["topic"] == "secret"
    assert body["title"] == "Software Engineer @ Google"
    assert body["priority"] == 4
    assert body["click"] == "https://careers.example/jobs/1"
    assert body["tags"] == ["briefcase"]


def test_ntfy_records_failure_without_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret"})

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


def test_ntfy_includes_summary_in_message() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret"})
    job = _job()
    job.summary = "Matches your search: mentions engineer."

    notifier.send(ctx, [job])

    assert "Matches your search: mentions engineer." in captured[0]["message"]


def test_ntfy_rejects_unsafe_server_url() -> None:
    notifier = NtfyNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="ntfy",
        config={"topic": "secret", "server_url": "http://127.0.0.1:6379"},
    )
    with pytest.raises(ValueError, match="not allowed|disallowed"):
        notifier.send(ctx, [_job()])


def test_ntfy_requires_topic() -> None:
    notifier = NtfyNotifier(client=httpx.Client())
    ctx = NotifyContext(target_type="ntfy", config={})
    with pytest.raises(ValueError, match="config.topic"):
        notifier.send(ctx, [_job()])


def test_ntfy_single_without_url_omits_click() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret"})
    job = JobPosting(external_id="1", title="Engineer")
    notifier.send(ctx, [job])
    assert "click" not in captured[0]
    assert captured[0]["message"] == "New job posting"


def test_ntfy_rejects_non_http_click_url() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret"})
    # Bypass ingest validation to assert render-side scheme gating (NTF-08).
    job = JobPosting.model_construct(
        external_id="1",
        title="Engineer",
        company="",
        location="",
        url="javascript:alert(1)",
        summary="",
        raw={},
    )
    notifier.send(ctx, [job])
    assert "click" not in captured[0]
    assert "javascript:" not in captured[0].get("message", "")


def test_ntfy_digest_empty_jobs_returns_empty() -> None:
    notifier = NtfyNotifier(client=httpx.Client())
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret"}, digest=True)
    assert notifier.send(ctx, []) == []


def test_ntfy_digest_records_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret"}, digest=True)
    results = notifier.send(ctx, [_job(), _job("2")])
    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


def test_ntfy_uses_auth_token_header() -> None:
    captured_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret", "token": "tk_1"})
    notifier.send(ctx, [_job()])
    assert captured_headers[0]["authorization"] == "Bearer tk_1"


def test_ntfy_close_behaviour() -> None:
    notifier = NtfyNotifier()
    notifier.close()
    assert notifier._client.is_closed

    client = httpx.Client()
    injected = NtfyNotifier(client=client)
    injected.close()
    assert not client.is_closed
    client.close()


def test_registry_resolves_ntfy() -> None:
    assert isinstance(get_notifier("ntfy"), NtfyNotifier)
