"""Unit tests for Slack/Discord markup escaping helpers."""

from app.notifiers.markup import (
    discord_markdown_link,
    escape_discord_markdown,
    escape_slack_mrkdwn,
    safe_http_url,
    slack_apply_link,
)


def test_escape_slack_mrkdwn_escapes_angle_brackets_and_ampersand() -> None:
    poisoned = "<https://evil.tld|Click> & more"
    assert escape_slack_mrkdwn(poisoned) == ("&lt;https://evil.tld|Click&gt; &amp; more")


def test_escape_discord_markdown_neutralizes_link_syntax() -> None:
    poisoned = "[Click me](https://evil.tld) *bold*"
    escaped = escape_discord_markdown(poisoned)
    assert "[Click me](https://evil.tld)" not in escaped
    assert escaped == "Click me(https://evil.tld) \\*bold\\*"


def test_safe_http_url_allows_http_https_only() -> None:
    assert safe_http_url("https://careers.example/jobs/1") == ("https://careers.example/jobs/1")
    assert safe_http_url("  http://careers.example/jobs/1  ") == ("http://careers.example/jobs/1")
    assert safe_http_url("javascript:alert(1)") is None
    assert safe_http_url("data:text/html,hi") is None
    assert safe_http_url("/relative") is None
    assert safe_http_url("https://") is None
    assert safe_http_url("") is None
    assert safe_http_url("   ") is None


def test_slack_apply_link_rejects_breakout_and_non_http() -> None:
    assert slack_apply_link("https://careers.example/1") == ("<https://careers.example/1|Apply>")
    assert slack_apply_link("https://evil.tld|Click>") is None
    assert slack_apply_link("javascript:alert(1)") is None


def test_discord_markdown_link_escapes_label_and_validates_url() -> None:
    assert discord_markdown_link("Engineer @ ACME", "https://jobs.example/1") == (
        "[Engineer @ ACME](https://jobs.example/1)"
    )
    link = discord_markdown_link("[phish](https://evil.tld)", "https://jobs.example/1")
    assert link == "[phish(https://evil.tld)](https://jobs.example/1)"
    assert discord_markdown_link("Engineer", "javascript:alert(1)") is None
