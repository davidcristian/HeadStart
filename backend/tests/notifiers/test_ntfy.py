import httpx

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
        assert str(request.url) == "https://ntfy.sh"
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(target_type="ntfy", config={"topic": "secret", "priority": "high"})

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


def test_registry_resolves_ntfy() -> None:
    assert isinstance(get_notifier("ntfy"), NtfyNotifier)
