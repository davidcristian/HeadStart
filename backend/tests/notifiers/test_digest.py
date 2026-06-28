import httpx

from app.notifiers import NotifyContext
from app.notifiers.adapters.ntfy import NtfyNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str) -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url=f"https://careers.example/jobs/{external_id}",
    )


def test_ntfy_digest_posts_single_batched_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "abc"})

    notifier = NtfyNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="ntfy",
        config={"topic": "secret"},
        digest=True,
        search_name="Backend roles",
    )

    results = notifier.send(ctx, [_job("1"), _job("2")])

    assert len(results) == 2
    assert all(r.status == "sent" for r in results)
    assert len(captured) == 1
    body = captured[0]
    assert body["title"] == "2 new jobs — Backend roles"
    assert "Software Engineer @ Google" in body["message"]
    assert "https://careers.example/jobs/1" in body["message"]
