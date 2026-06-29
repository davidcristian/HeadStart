"""Indeed job-search adapter.

Indeed embeds search results as JSON in the HTML response:
  window.mosaic.providerData["mosaic-provider-jobcards"] = {...}

Config / context:
  - `query_url`: full Indeed search URL (e.g. `https://www.indeed.com/jobs?q=python&l=remote`).
  - `config["q"]` / `config["l"]`: keyword and location when building the search URL.
  - `config["max_results"]`: cap on jobs fetched across pages (default 50).
  - `config["page_size"]`: results per page / pagination step (default 10).

Indeed often blocks unauthenticated HTTP clients (Cloudflare). When that happens,
save session cookies via Site credentials so the shared HttpClient can pass the
challenge.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from selectolax.parser import HTMLParser

from app.scrapers.base import Scraper, register_scraper
from app.scrapers.types import JobPosting, ScrapeContext

_MOSAIC_MARKERS = (
    'window.mosaic.providerData["mosaic-provider-jobcards"]=',
    "window.mosaic.providerData['mosaic-provider-jobcards']=",
)
_INDEED_HOST_RE = re.compile(r"^(?:[a-z]{2}|www)\.indeed\.com$|^indeed\.com$", re.IGNORECASE)
_CAPTCHA_MARKERS = (
    "INDEED_CLOUDFLARE_STATIC_PAGE",
    "Security Check - Indeed.com",
    "Additional Verification Required",
)
_DEFAULT_MAX_RESULTS = 50
_DEFAULT_PAGE_SIZE = 10
_MAX_RESULTS_CAP = 1000


@register_scraper("indeed")
class IndeedScraper(Scraper):
    """Fetch postings from an Indeed keyword/location search."""

    def fetch(self, ctx: ScrapeContext) -> list[JobPosting]:
        target = self._resolve(ctx)
        max_results = self._max_results(ctx.config)
        page_size = self._page_size(ctx.config)
        postings: list[JobPosting] = []
        seen: set[str] = set()
        offset = 0
        total_available: int | None = None

        while len(postings) < max_results:
            page_url = self._page_url(target.search_url, offset)
            html = self.http.get_text(page_url)
            self._reject_captcha(html)
            jobs, page_total = self._parse_page(html, target.origin)
            if total_available is None and page_total is not None:
                total_available = min(page_total, _MAX_RESULTS_CAP)
            if not jobs:
                break
            for job in jobs:
                key = job.external_id
                if key in seen:
                    continue
                seen.add(key)
                postings.append(job)
                if len(postings) >= max_results:
                    break
            offset += page_size
            if total_available is not None and offset >= total_available:
                break
            if total_available is None and len(jobs) < page_size:
                break

        return postings

    def _parse_page(self, html: str, origin: str) -> tuple[list[JobPosting], int | None]:
        mosaic = _extract_mosaic_payload(html)
        if mosaic is not None:
            model = mosaic.get("metaData", {}).get("mosaicProviderJobCardsModel", {})
            if isinstance(model, dict):
                results = model.get("results")
                total = _total_from_tiers(model.get("tierSummaries"))
                if isinstance(results, list):
                    postings = [
                        posting
                        for item in results
                        if isinstance(item, dict)
                        for posting in [_to_posting(item, origin)]
                        if posting is not None
                    ]
                    return postings, total
        return _parse_html_cards(html, origin), None

    @staticmethod
    def _reject_captcha(html: str) -> None:
        if any(marker in html for marker in _CAPTCHA_MARKERS):
            raise ValueError(
                "indeed returned a Cloudflare security page; add session cookies via "
                "Site credentials or retry later"
            )

    @staticmethod
    def _resolve(ctx: ScrapeContext) -> _SearchTarget:
        if ctx.query_url:
            parsed = urlparse(ctx.query_url.strip())
            host = parsed.netloc.lower()
            if not _INDEED_HOST_RE.match(host):
                raise ValueError("indeed scraper requires an indeed.com search URL")
            path = parsed.path.rstrip("/") or "/"
            if not path.startswith("/jobs"):
                raise ValueError("indeed scraper query_url must be a /jobs search page")
            origin = f"{parsed.scheme}://{parsed.netloc}"
            return _SearchTarget(search_url=ctx.query_url.strip(), origin=origin)

        config = ctx.config
        keyword = str(config.get("q") or config.get("keywords") or "").strip()
        location = str(config.get("l") or config.get("location") or "").strip()
        if not keyword and not location:
            raise ValueError("indeed scraper needs a query_url or config q/l")
        host = str(config.get("host") or "www.indeed.com").lower()
        params = {"q": keyword, "l": location, "filter": "0"}
        query = urlencode({k: v for k, v in params.items() if v})
        origin = f"https://{host}"
        return _SearchTarget(search_url=f"{origin}/jobs?{query}", origin=origin)

    @staticmethod
    def _page_url(search_url: str, start: int) -> str:
        if start <= 0:
            return search_url
        parsed = urlparse(search_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["start"] = [str(start)]
        query = urlencode({k: v[0] for k, v in params.items()})
        return urlunparse(parsed._replace(query=query))

    @staticmethod
    def _max_results(config: dict[str, Any]) -> int:
        raw = config.get("max_results", _DEFAULT_MAX_RESULTS)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("max_results must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("max_results must be a positive integer")
        return min(value, _MAX_RESULTS_CAP)

    @staticmethod
    def _page_size(config: dict[str, Any]) -> int:
        raw = config.get("page_size", _DEFAULT_PAGE_SIZE)
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("page_size must be a positive integer")
        value = int(raw)
        if value <= 0:
            raise ValueError("page_size must be a positive integer")
        return value


class _SearchTarget:
    __slots__ = ("search_url", "origin")

    def __init__(self, *, search_url: str, origin: str) -> None:
        self.search_url = search_url
        self.origin = origin


def _extract_mosaic_payload(html: str) -> dict[str, Any] | None:
    for marker in _MOSAIC_MARKERS:
        idx = html.find(marker)
        if idx == -1:
            continue
        start = html.find("{", idx + len(marker))
        if start == -1:
            continue
        blob = _balanced_json_object(html, start)
        if blob is None:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        return data if isinstance(data, dict) else None
    return None


def _balanced_json_object(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote:
                in_string = False
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _total_from_tiers(tiers: Any) -> int | None:
    if not isinstance(tiers, list):
        return None
    total = 0
    found = False
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        count = tier.get("jobCount")
        if isinstance(count, (int, float)) and not isinstance(count, bool):
            total += int(count)
            found = True
    return total if found else None


def _to_posting(job: dict[str, Any], origin: str) -> JobPosting | None:
    jobkey = str(job.get("jobkey") or "").strip()
    title = str(job.get("title") or job.get("displayTitle") or "").strip()
    if not jobkey or not title:
        return None
    company = str(job.get("company") or job.get("truncatedCompany") or "").strip()
    location = str(job.get("formattedLocation") or "").strip()
    url = _job_url(job, origin, jobkey)
    posted_at = None
    pub_date = job.get("pubDate")
    if isinstance(pub_date, (int, float)):
        posted_at = datetime.fromtimestamp(pub_date / 1000, tz=UTC)
    return JobPosting(
        external_id=jobkey,
        title=title,
        company=company,
        location=location,
        url=url,
        posted_at=posted_at,
        raw=job,
    )


def _job_url(job: dict[str, Any], origin: str, jobkey: str) -> str:
    link = str(job.get("viewJobLink") or "").strip()
    if link.startswith("http://") or link.startswith("https://"):
        return link
    if link.startswith("/"):
        return f"{origin}{link}"
    return f"{origin}/viewjob?jk={jobkey}"


def _parse_html_cards(html: str, origin: str) -> list[JobPosting]:
    tree = HTMLParser(html)
    postings: list[JobPosting] = []
    seen: set[str] = set()
    for node in tree.css("[data-jk]"):
        raw_key = (node.attributes or {}).get("data-jk")
        jobkey = raw_key.strip() if raw_key else ""
        if not jobkey or jobkey in seen:
            continue
        seen.add(jobkey)
        card = _card_root(node)
        title_node = card.css_first("h2.jobTitle span[title], h2.jobTitle a span, h2 a span")
        title = ""
        if title_node is not None:
            title = (title_node.attributes or {}).get("title") or title_node.text(strip=True)
        if not title:
            continue
        company_node = card.css_first("[data-testid='company-name'], .companyName")
        company = company_node.text(strip=True) if company_node else ""
        location_node = card.css_first("[data-testid='text-location'], .companyLocation")
        location = location_node.text(strip=True) if location_node else ""
        link_node = card.css_first("h2.jobTitle a[href], a.jcs-JobTitle, a[data-jk]")
        href = link_node.attributes.get("href", "") if link_node else ""
        url = _job_url({"viewJobLink": href}, origin, jobkey)
        postings.append(
            JobPosting(
                external_id=jobkey,
                title=title,
                company=company,
                location=location,
                url=url,
            )
        )
    return postings


_CARD_CLASS_TOKENS = ("job_seen_beacon", "resultContent", "jobsearch-SerpJobCard")


def _card_root(node: Any) -> Any:
    current = node
    while current.parent is not None:
        classes = (current.attributes or {}).get("class", "")
        if any(token in classes for token in _CARD_CLASS_TOKENS):
            return current
        current = current.parent
    return node
