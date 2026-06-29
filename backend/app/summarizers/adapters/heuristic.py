"""Heuristic (rule-based) summarizer — the offline default.

Builds a short "why this matches" blurb from the search's own filters: which
include-keywords appear, whether the location/workplace line up, etc. It needs
no API key or network, so it is safe everywhere (CI, local, prod) and is the
default provider.

Kept dependency-free on purpose (only stdlib + JobPosting): summarizers are an
edge subsystem, so the small amount of filter parsing here is duplicated rather
than imported from the services layer.
"""

from __future__ import annotations

import re

from app.scrapers.types import JobPosting
from app.summarizers.base import Summarizer, register_summarizer
from app.summarizers.types import SummaryContext


@register_summarizer("heuristic")
class HeuristicSummarizer(Summarizer):
    """Explain a match using the search filters, with no external calls."""

    def summarize(self, ctx: SummaryContext, jobs: list[JobPosting]) -> list[str]:
        return [self._blurb(ctx, job) for job in jobs]

    def _blurb(self, ctx: SummaryContext, job: JobPosting) -> str:
        reasons = self._reasons(ctx, job)
        if reasons:
            return "Matches your search: " + "; ".join(reasons) + "."
        return self._fallback(ctx, job)

    @staticmethod
    def _reasons(ctx: SummaryContext, job: JobPosting) -> list[str]:
        filters = ctx.filters or {}
        haystack = " ".join(part.lower() for part in (job.title, job.company, job.location) if part)
        reasons: list[str] = []

        include = _terms(filters.get("keywords_include")) or _terms(filters.get("keywords"))
        matched = [term for term in include if term in haystack]
        if matched:
            reasons.append("mentions " + ", ".join(_dedupe(matched)))

        workplaces = {
            wp for wp in (_workplace(token) for token in _terms(filters.get("workplace"))) if wp
        }
        if workplaces:
            inferred = _infer_workplace(job)
            if inferred in workplaces:
                reasons.append(f"{inferred} role")

        locations = _terms(filters.get("location"))
        if locations and job.location:
            location_text = job.location.lower()
            if any(term in location_text for term in locations):
                reasons.append(f"in {job.location}")

        return reasons

    @staticmethod
    def _fallback(ctx: SummaryContext, job: JobPosting) -> str:
        role = job.title or "New role"
        tail = f" at {job.company}" if job.company else ""
        if ctx.search_name:
            return f"New match for '{ctx.search_name}': {role}{tail}."
        return f"{role}{tail}."


def _terms(value: object) -> list[str]:
    """Split a filter value (string or list) into lowercase terms."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip().lower()
        return [part for part in re.split(r"[\s,]+", text) if part]
    if isinstance(value, list):
        terms: list[str] = []
        for item in value:
            terms.extend(_terms(item))
        return terms
    return _terms(str(value))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _workplace(token: str) -> str | None:
    token = token.replace("_", "-")
    if "remote" in token:
        return "remote"
    if "hybrid" in token:
        return "hybrid"
    if "onsite" in token or "on-site" in token:
        return "onsite"
    return None


def _infer_workplace(job: JobPosting) -> str | None:
    for source in (job.location, job.title):
        text = source.lower()
        if re.search(r"\bremote\b", text):
            return "remote"
        if re.search(r"\bhybrid\b", text):
            return "hybrid"
        if re.search(r"\bon[- ]?site\b", text):
            return "onsite"
    return None
