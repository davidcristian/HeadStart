"""Escape helpers for channel markup built from untrusted job fields."""

from __future__ import annotations

from urllib.parse import urlparse

# Slack mrkdwn link form is <url|label>; these break out of the URL segment.
_SLACK_LINK_BREAKERS = frozenset("<>|")


def escape_slack_mrkdwn(text: str) -> str:
    """Escape Slack mrkdwn special characters in untrusted plain text."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_discord_markdown(text: str) -> str:
    """Neutralize Discord markdown link/emphasis metacharacters in untrusted text.

    Link brackets are stripped (not backslash-escaped) so a poisoned label cannot
    close a surrounding `[label](url)` early when used inside digest links.
    """
    cleaned = text.replace("[", "").replace("]", "")
    return (
        cleaned.replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("~", "\\~")
        .replace("|", "\\|")
        .replace(">", "\\>")
    )


def safe_http_url(url: str) -> str | None:
    """Return a trimmed http(s) URL with a host, or None if unsafe for links."""
    stripped = url.strip()
    if not stripped:
        return None
    parsed = urlparse(stripped)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return stripped


def slack_apply_link(url: str) -> str | None:
    """Build a Slack mrkdwn Apply link, or None when the URL is not link-safe."""
    safe = safe_http_url(url)
    if safe is None or any(ch in safe for ch in _SLACK_LINK_BREAKERS):
        return None
    return f"<{safe}|Apply>"


def discord_markdown_link(label: str, url: str) -> str | None:
    """Build a Discord `[label](url)` link, or None when the URL is not link-safe."""
    safe = safe_http_url(url)
    if safe is None:
        return None
    return f"[{escape_discord_markdown(label)}]({safe})"
