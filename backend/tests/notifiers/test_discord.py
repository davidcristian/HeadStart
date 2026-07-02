import json

import httpx
import pytest

from app.notifiers import NotifyContext, get_notifier
from app.notifiers.adapters.discord import DiscordNotifier
from app.scrapers.types import JobPosting


def _job(external_id: str = "1") -> JobPosting:
    return JobPosting(
        external_id=external_id,
        title="Software Engineer",
        company="Google",
        location="Amsterdam",
        url="https://careers.example/jobs/1",
    )


def test_discord_posts_expected_payload() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        assert str(request.url) == "https://discord.com/api/webhooks/123/secret"
        return httpx.Response(204)

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.com/api/webhooks/123/secret"},
    )

    results = notifier.send(ctx, [_job()])

    assert len(results) == 1
    assert results[0].status == "sent"
    embed = captured[0]["embeds"][0]
    assert embed["title"] == "Software Engineer @ Google"
    assert "Google" in embed["description"]
    assert "Amsterdam" in embed["description"]
    assert embed["url"] == "https://careers.example/jobs/1"
    assert embed["color"] == 0x5865F2


def test_discord_records_failure_without_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    notifier = DiscordNotifier(client=httpx.Client(transport=httpx.MockTransport(handler)))
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "https://discord.com/api/webhooks/123/secret"},
    )

    results = notifier.send(ctx, [_job(), _job("2")])

    assert [r.status for r in results] == ["failed", "failed"]
    assert results[0].error


def test_discord_requires_webhook_url() -> None:
    notifier = DiscordNotifier(client=httpx.Client())
    ctx = NotifyContext(target_type="discord", config={})

    try:
        notifier.send(ctx, [_job()])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "webhook_url" in str(exc)


def test_discord_rejects_unsafe_url() -> None:
    notifier = DiscordNotifier(client=httpx.Client())
    ctx = NotifyContext(
        target_type="discord",
        config={"webhook_url": "http://127.0.0.1/hook"},
    )
    with pytest.raises(ValueError, match="not allowed|disallowed"):
        notifier.send(ctx, [_job()])


def test_registry_resolves_discord() -> None:
    assert isinstance(get_notifier("discord"), DiscordNotifier)
