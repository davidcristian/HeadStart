import json

import httpx

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.slack import SlackNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
    )


def test_slack_posts_expected_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert str(request.url) == "https://hooks.slack.com/services/T00/B00/secret"
        return httpx.Response(200, text="ok")

    notifier = SlackNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="slack",
        config={"webhook_url": "https://hooks.slack.com/services/T00/B00/secret"},
    )

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    body = captured[0]
    assert "*Software Engineer* @ Google" in body["text"]
    assert "Amsterdam" in body["text"]
    assert "<https://careers.example/jobs/1|Apply>" in body["text"]
    assert body["blocks"][0]["text"]["type"] == "mrkdwn"


def test_slack_records_failure_without_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = SlackNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="slack",
        config={"webhook_url": "https://hooks.slack.com/services/T00/B00/secret"},
    )

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


def test_slack_requires_webhook_url() -> None:
    notifier = SlackNotifier(client=httpx.Client())
    ctx = NotifyContext(target_type="slack", config={})

    try:
        notifier.send(ctx, [_job()])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "webhook_url" in str(exc)


def test_slack_digest_includes_summary() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, text="ok")

    notifier = SlackNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="slack",
        config={"webhook_url": "https://hooks.slack.com/services/T00/B00/secret"},
        digest=True,
        search_name="Backend roles",
    )
    job = _job()
    job.summary = "Matches your search: mentions engineer."

    notifier.send(ctx, [job])

    text = captured[0]["text"]
    assert "2 new jobs" not in text  # single job digest
    assert "Matches your search: mentions engineer." in text
    assert "<https://careers.example/jobs/1|Apply>" in text


def test_registry_resolves_slack() -> None:
    assert isinstance(get_notifier("slack"), SlackNotifier)
