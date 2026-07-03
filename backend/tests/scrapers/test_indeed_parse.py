"""Unit tests for the Indeed HTML/JSON parsing helpers.

These exercise the parse-module branches directly (malformed payloads, the
balanced-brace scanner, tier totals, and the HTML-card fallback) that the
scraper-level tests in ``test_indeed.py`` do not reach.
"""

import pytest

from app.scrapers.adapters.indeed_parse import (
    _balanced_json_object,
    _card_root,
    _job_url,
    _to_posting,
    _total_from_tiers,
    parse_page,
    reject_captcha,
)

ORIGIN = "https://www.indeed.com"


def _mosaic(inner: str) -> str:
    return (
        "<html><body><script>"
        'window.mosaic.providerData["mosaic-provider-jobcards"]='
        f"{inner}"
        "</script></body></html>"
    )


def test_reject_captcha_passes_clean_html() -> None:
    reject_captcha("<html>ok</html>")  # no exception


def test_reject_captcha_raises_on_security_page() -> None:
    with pytest.raises(ValueError, match="Cloudflare"):
        reject_captcha("<html>Security Check - Indeed.com</html>")


def test_parse_page_model_not_dict_falls_back_to_html_cards() -> None:
    html = _mosaic('{"metaData":{"mosaicProviderJobCardsModel":"nope"}}')
    postings, total = parse_page(html, ORIGIN)
    assert postings == []
    assert total is None


def test_parse_page_results_not_list_falls_back_to_html_cards() -> None:
    html = _mosaic('{"metaData":{"mosaicProviderJobCardsModel":{"results":"nope"}}}')
    postings, total = parse_page(html, ORIGIN)
    assert postings == []
    assert total is None


def test_parse_page_marker_without_object_falls_through() -> None:
    # Marker present but no '{' after it -> _extract_mosaic_payload continues.
    html = (
        "<html><body><script>"
        'window.mosaic.providerData["mosaic-provider-jobcards"]=null;'
        "</script></body></html>"
    )
    postings, total = parse_page(html, ORIGIN)
    assert postings == []
    assert total is None


def test_parse_page_unbalanced_braces_falls_through() -> None:
    html = _mosaic('{"metaData":{"mosaicProviderJobCardsModel":{')
    postings, total = parse_page(html, ORIGIN)
    assert postings == []
    assert total is None


def test_parse_page_invalid_json_falls_through() -> None:
    # Balanced braces but not valid JSON -> JSONDecodeError branch.
    html = _mosaic("{not valid json}")
    postings, total = parse_page(html, ORIGIN)
    assert postings == []
    assert total is None


def test_parse_page_json_with_escaped_quotes_and_backslashes() -> None:
    # Exercises the in-string escape handling of the balanced-brace scanner:
    # the title contains an escaped quote and a backslash, and there is a stray
    # '}' inside the string that must NOT close the object early.
    inner = (
        '{"metaData":{"mosaicProviderJobCardsModel":{"results":['
        '{"jobkey":"esc1","title":"A \\"quoted\\" role } \\\\ end",'
        '"formattedLocation":"Remote","viewJobLink":"/viewjob?jk=esc1"}'
        "]}}}"
    )
    postings, _ = parse_page(_mosaic(inner), ORIGIN)
    assert len(postings) == 1
    assert postings[0].external_id == "esc1"


def test_balanced_json_object_returns_none_when_never_closed() -> None:
    assert _balanced_json_object("{ unterminated", 0) is None


def test_total_from_tiers_non_list_returns_none() -> None:
    assert _total_from_tiers("nope") is None


def test_total_from_tiers_skips_non_dict_and_invalid_counts() -> None:
    # A non-dict entry is skipped, and a dict whose jobCount is a bool/str does
    # not count (loop back-edge 110->106); only real numbers accumulate.
    tiers = ["skip-me", {"jobCount": True}, {"jobCount": "x"}, {"jobCount": 4}]
    assert _total_from_tiers(tiers) == 4


def test_total_from_tiers_all_invalid_returns_none() -> None:
    assert _total_from_tiers([{"noCount": 1}]) is None


def test_to_posting_returns_none_without_key_or_title() -> None:
    assert _to_posting({"jobkey": "", "title": "Role"}, ORIGIN) is None
    assert _to_posting({"jobkey": "k", "title": ""}, ORIGIN) is None


def test_to_posting_without_numeric_pub_date() -> None:
    posting = _to_posting({"jobkey": "k", "title": "Role", "pubDate": "not-a-number"}, ORIGIN)
    assert posting is not None
    assert posting.posted_at is None


def test_to_posting_with_numeric_pub_date() -> None:
    posting = _to_posting({"jobkey": "k", "title": "Role", "pubDate": 1700000000000}, ORIGIN)
    assert posting is not None
    assert posting.posted_at is not None


def test_job_url_variants() -> None:
    assert _job_url({"viewJobLink": "https://x.co/j/1"}, ORIGIN, "k") == "https://x.co/j/1"
    assert _job_url({"viewJobLink": "/viewjob?jk=k"}, ORIGIN, "k") == f"{ORIGIN}/viewjob?jk=k"
    # A bare relative link (no leading slash, not http) -> canonical fallback.
    assert _job_url({"viewJobLink": "relative"}, ORIGIN, "k") == f"{ORIGIN}/viewjob?jk=k"


def test_parse_html_cards_skips_missing_key_dup_and_empty_title() -> None:
    html = """
    <div class="job_seen_beacon">
      <a data-jk=""><span title="No Key">No Key</span></a>
    </div>
    <div class="job_seen_beacon">
      <h2 class="jobTitle"><a href="/viewjob?jk=dup" data-jk="dup">
        <span title="First">First</span></a></h2>
    </div>
    <div class="job_seen_beacon">
      <h2 class="jobTitle"><a href="/viewjob?jk=dup" data-jk="dup">
        <span title="Duplicate">Duplicate</span></a></h2>
    </div>
    <div class="job_seen_beacon">
      <a data-jk="notitle"></a>
    </div>
    """
    postings, total = parse_page(html, ORIGIN)
    assert [p.external_id for p in postings] == ["dup"]
    assert postings[0].title == "First"
    assert total is None


def test_parse_html_cards_empty_title_text_is_skipped() -> None:
    # data-jk present, title node found but resolves to empty text/title -> skip.
    html = """
    <div class="job_seen_beacon">
      <h2 class="jobTitle"><a data-jk="blank"><span></span></a></h2>
    </div>
    """
    postings, _ = parse_page(html, ORIGIN)
    assert postings == []


def test_card_root_returns_node_when_no_card_ancestor() -> None:
    from selectolax.parser import HTMLParser

    node = HTMLParser("<div><a data-jk='x'>hi</a></div>").css_first("[data-jk]")
    assert _card_root(node) is node
