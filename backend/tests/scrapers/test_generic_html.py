import httpx

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
