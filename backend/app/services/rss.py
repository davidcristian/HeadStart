"""RSS 2.0 feed serialization for the jobs feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from email.utils import format_datetime
from xml.sax.saxutils import escape

from app.models.seen_job import SeenJob


@dataclass(frozen=True)
class RssChannel:
    title: str
    link: str
    description: str
    jobs: list[SeenJob]


def build_rss_feed(channel: RssChannel) -> str:
    """Render jobs as an RSS 2.0 XML document."""
    items = "\n".join(_render_item(job) for job in channel.jobs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{escape(channel.title)}</title>\n"
        f"    <link>{escape(channel.link)}</link>\n"
        f"    <description>{escape(channel.description)}</description>\n"
        f"{items}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def _render_item(job: SeenJob) -> str:
    title = job.title or "Untitled job"
    link = job.url or ""
    description_parts = [part for part in (job.company, job.location, job.status) if part]
    description = " · ".join(description_parts) if description_parts else job.status
    seen_at = job.first_seen_at
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=UTC)
    pub_date = format_datetime(seen_at, usegmt=True)
    guid = link or f"jobnotifier:{job.id}"
    return (
        "    <item>\n"
        f"      <title>{escape(title)}</title>\n"
        f"      <link>{escape(link)}</link>\n"
        f"      <description>{escape(description)}</description>\n"
        f"      <pubDate>{escape(pub_date)}</pubDate>\n"
        f'      <guid isPermaLink="{"true" if link else "false"}">{escape(guid)}</guid>\n'
        "    </item>"
    )
