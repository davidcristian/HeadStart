import httpx

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def test_shopify_careers_parses_postings() -> None:
    fixture = load_fixture("shopify_careers.html")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.shopify.com"
        assert request.url.path.startswith("/careers")
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("shopify_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            query_url="https://www.shopify.com/careers",
            config={"company": "Shopify"},
        )
    )

    assert len(postings) == 2
    first = postings[0]
    assert first.external_id == "7a204574-fb6c-4b27-84f3-d2a693739b18"
    assert first.title == "Account Executive"
    assert first.company == "Shopify"
    assert first.location == "Remote - Global"
    assert (
        first.url
        == "https://www.shopify.com/careers?ashby_jid=7a204574-fb6c-4b27-84f3-d2a693739b18"
    )
    assert first.posted_at is not None
    assert postings[1].title == "Workplace Technology Manager"


def test_shopify_careers_filters_keywords_client_side() -> None:
    fixture = load_fixture("shopify_careers.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("shopify_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            config={"company": "Shopify", "q": "workplace"},
        )
    )

    assert len(postings) == 1
    assert postings[0].title == "Workplace Technology Manager"


def test_shopify_careers_reads_keyword_from_filters() -> None:
    fixture = load_fixture("shopify_careers.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("shopify_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(
            filters={"keywords_include": "account"},
            config={"company": "Shopify"},
        )
    )

    assert len(postings) == 1
    assert postings[0].title == "Account Executive"
