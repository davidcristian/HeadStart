"""RSS 2.0 feed serialization for the jobs feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from email.utils import format_datetime
from xml.sax.saxutils import escape

from app.models.seen_job import SeenJob

# XML 1.0 Char production excludes most C0 controls; keep tab/LF/CR only.
_XML_INVALID_CONTROLS = dict.fromkeys(
    (*range(0x00, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20)),
    None,
)


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
        f"    <title>{_xml_text(channel.title)}</title>\n"
        f"    <link>{_xml_text(channel.link)}</link>\n"
        f"    <description>{_xml_text(channel.description)}</description>\n"
        f"{items}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def _xml_text(value: str) -> str:
    """Strip XML-invalid C0 controls, then escape markup specials."""
    return escape(value.translate(_XML_INVALID_CONTROLS))


def _render_item(job: SeenJob) -> str:
    title = job.title or "Untitled job"
    link = job.url or ""
    description_fields = (job.company, job.location, job.salary, job.status)
    description_parts = [part for part in description_fields if part]
    description = " · ".join(description_parts) if description_parts else job.status
    if job.summary:
        description = f"{job.summary}. {description}"
    seen_at = job.first_seen_at
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=UTC)
    pub_date = format_datetime(seen_at, usegmt=True)
    guid = link or f"headstart:{job.id}"
    return (
        "    <item>\n"
        f"      <title>{_xml_text(title)}</title>\n"
        f"      <link>{_xml_text(link)}</link>\n"
        f"      <description>{_xml_text(description)}</description>\n"
        f"      <pubDate>{_xml_text(pub_date)}</pubDate>\n"
        f'      <guid isPermaLink="{"true" if link else "false"}">{_xml_text(guid)}</guid>\n'
        "    </item>"
    )
