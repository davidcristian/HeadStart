"""Generic CSS-selector HTML adapter.

For simple, static careers pages. The user supplies selectors from the UI (no
code change needed). Config shape:

    {
      "item": ".job-listing",         # selector for each posting (required)
      "title": ".job-title",          # text selector, relative to item
      "url": "a",                      # element whose href is the link
      "company": ".company",          # optional
      "location": ".location",         # optional
      "base_url": "https://x.com"      # to resolve relative hrefs (optional)
    }

`external_id` defaults to the resolved URL, which is stable for dedup.
"""

from typing import Any
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext


@register_scraper("generic_html")
class GenericHtmlScraper(Scraper):
    """Parse postings from arbitrary HTML using configured CSS selectors."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        cfg = ctx.config
        item_sel = cfg.get("item")
        if not item_sel:
            raise ValueError("generic_html scraper requires config.item (a CSS selector)")
        if not ctx.query_url:
            raise ValueError("generic_html scraper requires a query_url")

        base_url = str(cfg.get("base_url") or ctx.query_url)
        html = self.http.get_text(ctx.query_url)
        tree = HTMLParser(html)

        postings: list[JobPosting] = []
        for node in tree.css(item_sel):
            posting = self._parse_item(node, cfg, base_url)
            if posting is not None:
                postings.append(posting)
        return postings

    def _parse_item(self, node: Node, cfg: dict[str, Any], base_url: str) -> JobPosting | None:
        title = self._text(node, cfg.get("title"))
        url = self._href(node, cfg.get("url"), base_url)
        if not title and not url:
            return None
        return JobPosting(
            external_id=url or title,
            title=title,
            company=self._text(node, cfg.get("company")),
            location=self._text(node, cfg.get("location")),
            url=url,
        )

    @staticmethod
    def _text(node: Node, selector: str | None) -> str:
        if not selector:
            return ""
        found = node.css_first(selector)
        return found.text(strip=True) if found else ""

    @staticmethod
    def _href(node: Node, selector: str | None, base_url: str) -> str:
        target = node.css_first(selector) if selector else node
        if target is None:
            return ""
        href = target.attributes.get("href") if target.attributes else None
        if not href:
            return ""
        return urljoin(base_url, href)
