"""URL helpers for comparing job postings across searches."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_QUERY_KEYS = frozenset({"ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid"})


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
