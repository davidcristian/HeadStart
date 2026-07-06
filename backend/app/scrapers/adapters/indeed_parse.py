"""Indeed HTML/JSON parsing helpers for the job-search scraper."""

from __future__ import annotations

import json
from typing import Any

from selectolax.parser import HTMLParser

from app.scrapers.dates import parse_epoch_millis
from app.scrapers.types import JobPosting

_MOSAIC_MARKERS = (
    'window.mosaic.providerData["mosaic-provider-jobcards"]=',
    "window.mosaic.providerData['mosaic-provider-jobcards']=",
)
_CAPTCHA_MARKERS = (
    "INDEED_CLOUDFLARE_STATIC_PAGE",
    "Security Check - Indeed.com",
    "Additional Verification Required",
)
_CARD_CLASS_TOKENS = ("job_seen_beacon", "resultContent", "jobsearch-SerpJobCard")


def reject_captcha(html: str) -> None:
    if any(marker in html for marker in _CAPTCHA_MARKERS):
        raise ValueError(
            "indeed returned a Cloudflare security page; add session cookies via "
            "Site credentials or retry later"
        )


def parse_page(html: str, origin: str) -> tuple[list[JobPosting], int | None]:
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
    posted_at = parse_epoch_millis(job.get("pubDate"))
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


def _card_root(node: Any) -> Any:
    current = node
    while current.parent is not None:
        classes = (current.attributes or {}).get("class", "")
        if any(token in classes for token in _CARD_CLASS_TOKENS):
            return current
        current = current.parent
    return node
