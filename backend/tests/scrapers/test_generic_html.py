import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import make_http_client

SAMPLE_HTML = """
<html><body>
  <ul>
    <li class="job">
      <a class="title" href="/jobs/1">Backend Engineer</a>
      <span class="loc">Amsterdam</span>
    </li>
    <li class="job">
      <a class="title" href="https://x.test/jobs/2">Frontend Engineer</a>
      <span class="loc">Remote</span>
    </li>
  </ul>
</body></html>
"""


def test_generic_html_extracts_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_HTML)

    scraper = get_scraper("generic_html", http=make_http_client(handler))
    ctx = ScrapeContext(
        query_url="https://x.test/careers",
        config={
            "item": "li.job",
            "title": "a.title",
            "url": "a.title",
            "location": "span.loc",
            "base_url": "https://x.test",
        },
    )
    postings = scraper.fetch(ctx)

    assert [p.title for p in postings] == ["Backend Engineer", "Frontend Engineer"]
    # Relative and absolute hrefs both resolve to absolute URLs.
    assert postings[0].url == "https://x.test/jobs/1"
    assert postings[1].url == "https://x.test/jobs/2"
    assert postings[0].location == "Amsterdam"
    # external_id defaults to the resolved URL (stable for dedup).
    assert postings[0].external_id == "https://x.test/jobs/1"


def test_generic_html_requires_item_selector() -> None:
    scraper = get_scraper("generic_html", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="requires config.item"):
        scraper.fetch(ScrapeContext(query_url="https://x.test/careers", config={}))


def test_generic_html_requires_query_url() -> None:
    scraper = get_scraper("generic_html", http=make_http_client(lambda _: httpx.Response(200)))
    with pytest.raises(ValueError, match="requires a query_url"):
        scraper.fetch(ScrapeContext(config={"item": "li.job"}))


def test_generic_html_defaults_base_url_to_query_url() -> None:
    html = '<ul><li class="job"><a class="title" href="/jobs/9">Eng</a></li></ul>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = get_scraper("generic_html", http=make_http_client(handler))
    ctx = ScrapeContext(
        query_url="https://x.test/careers",
        config={"item": "li.job", "title": "a.title", "url": "a.title"},
    )
    postings = scraper.fetch(ctx)
    assert postings[0].url == "https://x.test/jobs/9"


def test_generic_html_skips_items_without_title_or_url() -> None:
    """An item with neither a title nor a URL yields no posting (loop back-edge)."""
    html = """
    <ul>
      <li class="job"><span class="loc">Nowhere</span></li>
      <li class="job"><a class="title" href="/jobs/1">Real Job</a></li>
    </ul>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = get_scraper("generic_html", http=make_http_client(handler))
    ctx = ScrapeContext(
        query_url="https://x.test/careers",
        config={
            "item": "li.job",
            "title": "a.title",
            "url": "a.title",
            "location": "span.loc",
        },
    )
    postings = scraper.fetch(ctx)
    assert [p.title for p in postings] == ["Real Job"]


def test_generic_html_missing_href_element_and_attribute() -> None:
    """A url selector that matches nothing, and an element without href, both yield ''."""
    html = """
    <ul>
      <li class="job">
        <span class="title">No Link Here</span>
        <a class="broken">No href attr</a>
      </li>
    </ul>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = get_scraper("generic_html", http=make_http_client(handler))
    ctx = ScrapeContext(
        query_url="https://x.test/careers",
        config={
            "item": "li.job",
            "title": "span.title",
            # Selector matches no element -> _href target is None (line 74).
            "url": "a.missing",
        },
    )
    postings = scraper.fetch(ctx)
    assert len(postings) == 1
    assert postings[0].url == ""
    assert postings[0].external_id == "No Link Here"


def test_generic_html_element_without_href_attribute() -> None:
    """An element matched by the url selector but lacking href resolves to ''."""
    html = '<ul><li class="job"><a class="title">Titled Anchor</a></li></ul>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    scraper = get_scraper("generic_html", http=make_http_client(handler))
    ctx = ScrapeContext(
        query_url="https://x.test/careers",
        config={"item": "li.job", "title": "a.title", "url": "a.title"},
    )
    postings = scraper.fetch(ctx)
    assert postings[0].url == ""
    assert postings[0].title == "Titled Anchor"
