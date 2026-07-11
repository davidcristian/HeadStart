"""URL helpers for comparing job postings across searches."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_QUERY_KEYS = frozenset({"ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid"})


def safe_http_job_url(url: str) -> str | None:
    """Return a trimmed http(s) URL with a host, or None if unsafe for links.

    Scraped apply URLs are untrusted. Notifiers and ingest must reject
    non-http(s) schemes (javascript:, data:, relative paths) so poisoned
    postings cannot become clickable Apply links in trusted channels.
    """
    stripped = url.strip()
    if not stripped:
        return None
    parsed = urlparse(stripped)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return stripped


def normalize_job_url(url: str) -> str:
    """Return a canonical form of a job URL for cross-search dedup."""
    url = url.strip()
    if not url:
        return ""

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/").lower()

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_QUERY_KEYS
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)

    return urlunparse((scheme, netloc, path, "", query, ""))
