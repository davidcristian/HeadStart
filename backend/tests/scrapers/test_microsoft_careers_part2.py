import json

import httpx
import pytest

from app.scrapers import ScrapeContext, get_scraper
from tests.conftest import load_fixture, make_http_client


def _page(job_ids: list[int], count: int) -> dict[str, object]:
    return {
        "data": {
            "positions": [
                {"id": jid, "name": f"Job {jid}", "positionUrl": f"/careers/job/{jid}"}
                for jid in job_ids
            ],
            "count": count,
        }
    }


def test_microsoft_careers_paginates_full_pages() -> None:
    # Two full pages (page_size == len(positions)) with distinct ids so the
    # short-page guard is False and the loop continues (81->55).
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["start"])
        calls.append(start)
        if start == 0:
            return httpx.Response(200, json=_page([1, 2], count=4))
        return httpx.Response(200, json=_page([3, 4], count=4))

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 2}))
    assert {p.external_id for p in postings} == {"1", "2", "3", "4"}
    assert calls == [0, 2]


def test_microsoft_careers_skips_duplicate_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["start"])
        if start == 0:
            return httpx.Response(200, json=_page([1, 2], count=4))
        return httpx.Response(200, json=_page([2, 3], count=4))

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 2}))
    assert {p.external_id for p in postings} == {"1", "2", "3"}


def test_microsoft_careers_stops_on_empty_positions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([], count=10))

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    assert scraper.fetch(ScrapeContext(config={"company": "Microsoft"})) == []


def test_microsoft_careers_stops_when_start_reaches_total() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(int(request.url.params["start"]))
        return httpx.Response(200, json=_page([1, 2], count=2))

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 2}))
    assert len(postings) == 2
    assert calls == [0]


def test_microsoft_careers_stops_when_max_results_reached_mid_page() -> None:
    # max_results hit inside the for-loop (line 77 break); neither pagination
    # guard fires, so the while condition is re-checked and is false (55->84).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([1, 2, 3, 4, 5], count=100))

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    postings = scraper.fetch(
        ScrapeContext(config={"company": "Microsoft", "page_size": 5, "max_results": 2})
    )
    assert len(postings) == 2


def test_microsoft_careers_accepts_pcsx_api_url() -> None:
    fixture = load_fixture("microsoft_careers_search.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, text=fixture)

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    scraper.fetch(
        ScrapeContext(
            query_url=(
                "https://apply.careers.microsoft.com/api/pcsx/search"
                "?domain=contoso.com&q=cloud&location=Dublin"
            ),
            config={"company": "Microsoft"},
        )
    )

    assert "domain=contoso.com" in seen["url"]
    assert "query=cloud" in seen["url"]
    assert "location=Dublin" in seen["url"]


def test_microsoft_careers_rejects_foreign_host() -> None:
    scraper = get_scraper("microsoft_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="apply.careers.microsoft.com URL"):
        scraper.fetch(ScrapeContext(query_url="https://example.com/careers"))


def test_microsoft_careers_keyword_defaults_empty() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_page([], count=0))

    scraper = get_scraper("microsoft_careers", http=make_http_client(handler))
    # Empty keyword source values are skipped; falls through to "".
    scraper.fetch(ScrapeContext(config={"company": "Microsoft", "q": ""}))
    assert "query=&" in seen["url"] or seen["url"].endswith("query=")


def test_microsoft_careers_rejects_bad_page_size() -> None:
    scraper = get_scraper("microsoft_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"page_size": True}))


def test_microsoft_careers_rejects_non_positive_page_size() -> None:
    scraper = get_scraper("microsoft_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="page_size must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"page_size": 0}))


def test_microsoft_careers_rejects_bad_max_results() -> None:
    scraper = get_scraper("microsoft_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"max_results": "many"}))


def test_microsoft_careers_rejects_non_positive_max_results() -> None:
    scraper = get_scraper("microsoft_careers", http=make_http_client(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="max_results must be a positive integer"):
        scraper.fetch(ScrapeContext(config={"max_results": -1}))


def test_microsoft_careers_rejects_non_object_payload() -> None:
    scraper = get_scraper(
        "microsoft_careers", http=make_http_client(lambda r: httpx.Response(200, json=[1, 2]))
    )
    with pytest.raises(ValueError, match="expected object"):
        scraper.fetch(ScrapeContext(config={"company": "Microsoft"}))


def test_microsoft_careers_rejects_bad_data_field() -> None:
    scraper = get_scraper(
        "microsoft_careers",
        http=make_http_client(lambda r: httpx.Response(200, json={"data": "nope"})),
    )
    with pytest.raises(ValueError, match="unexpected data field"):
        scraper.fetch(ScrapeContext(config={"company": "Microsoft"}))


def test_microsoft_careers_rejects_bad_positions_field() -> None:
    scraper = get_scraper(
        "microsoft_careers",
        http=make_http_client(lambda r: httpx.Response(200, json={"data": {"positions": "nope"}})),
    )
    with pytest.raises(ValueError, match="unexpected positions field"):
        scraper.fetch(ScrapeContext(config={"company": "Microsoft"}))


def test_microsoft_careers_missing_id_raises() -> None:
    payload = {"data": {"positions": [{"name": "No id"}], "count": 1}}
    scraper = get_scraper(
        "microsoft_careers", http=make_http_client(lambda r: httpx.Response(200, json=payload))
    )
    with pytest.raises(ValueError, match="missing id"):
        scraper.fetch(ScrapeContext(config={"company": "Microsoft"}))


def test_microsoft_careers_count_falls_back_to_len() -> None:
    # Non-numeric count -> falls back to len(positions); short page ends loop.
    payload = {
        "data": {
            "positions": [{"id": 1, "name": "A"}],
            "count": "not-a-number",
        }
    }
    scraper = get_scraper(
        "microsoft_careers", http=make_http_client(lambda r: httpx.Response(200, json=payload))
    )
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 5}))
    assert len(postings) == 1


def test_microsoft_careers_location_and_url_fallbacks() -> None:
    payload = {
        "data": {
            "positions": [
                {"id": 1, "name": "Absolute", "positionUrl": "https://x.test/job/1"},
                {"id": 2, "name": "Locations only", "locations": ["Remote", "", "London"]},
                {"id": 3, "name": "No url or id-url"},
                {"id": 4, "name": "Bad ts", "postedTs": "nope"},
                {"id": 5, "name": "Relative-no-slash", "positionUrl": "careers/job/5"},
            ],
            "count": 5,
        }
    }
    scraper = get_scraper(
        "microsoft_careers", http=make_http_client(lambda r: httpx.Response(200, json=payload))
    )
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 5}))
    by_id = {p.external_id: p for p in postings}
    assert by_id["1"].url == "https://x.test/job/1"
    assert by_id["2"].location == "Remote; London"
    assert by_id["2"].url == "https://apply.careers.microsoft.com/careers/job/2"
    assert by_id["4"].posted_at is None
    assert by_id["5"].url == "https://apply.careers.microsoft.com/careers/job/5"


def test_microsoft_careers_url_origin_fallback_when_no_url_no_id() -> None:
    # positionUrl empty and id falsy -> job_url returns origin + careers path.
    payload = {"data": {"positions": [{"id": 0, "displayJobId": "D9", "name": "X"}], "count": 1}}
    scraper = get_scraper(
        "microsoft_careers", http=make_http_client(lambda r: httpx.Response(200, json=payload))
    )
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 5}))
    assert postings[0].external_id == "D9"
    assert postings[0].url == "https://apply.careers.microsoft.com/careers"


def test_microsoft_careers_standardized_locations_used_first() -> None:
    body = json.loads(load_fixture("microsoft_careers_search.json"))
    scraper = get_scraper(
        "microsoft_careers", http=make_http_client(lambda r: httpx.Response(200, json=body))
    )
    postings = scraper.fetch(ScrapeContext(config={"company": "Microsoft", "page_size": 5}))
    assert postings[0].location == "Redmond, WA, US"
