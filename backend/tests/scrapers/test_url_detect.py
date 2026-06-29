"""Tests for careers-page URL detection."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_greenhouse_board_url() -> None:
    result = detect_source_from_url("https://boards.greenhouse.io/acme-corp/jobs/123")
    assert result is not None
    assert result.adapter_key == "greenhouse"
    assert result.default_config["board_token"] == "acme-corp"
    assert result.base_url == "https://boards.greenhouse.io/acme-corp"
    assert result.query_url == "https://boards.greenhouse.io/acme-corp"


def test_detect_greenhouse_api_url() -> None:
    result = detect_source_from_url(
        "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true"
    )
    assert result is not None
    assert result.default_config["board_token"] == "example"


def test_detect_lever_board_url() -> None:
    result = detect_source_from_url(
        "https://jobs.lever.co/stripe",
        page_title="Stripe Careers",
    )
    assert result is not None
    assert result.adapter_key == "lever"
    assert result.default_config["site"] == "stripe"
    assert result.suggested_name == "Stripe"
    assert "region" not in result.default_config


def test_detect_lever_eu_board_url() -> None:
    result = detect_source_from_url("https://jobs.eu.lever.co/acme")
    assert result is not None
    assert result.default_config["region"] == "eu"


def test_detect_ashby_board_url() -> None:
    result = detect_source_from_url("https://jobs.ashbyhq.com/notion")
    assert result is not None
    assert result.adapter_key == "ashby"
    assert result.default_config["board"] == "notion"


def test_detect_workday_board_url() -> None:
    result = detect_source_from_url("https://acme.wd5.myworkdayjobs.com/en-US/External/jobs/123")
    assert result is not None
    assert result.adapter_key == "workday"
    assert result.default_config["tenant"] == "acme"
    assert result.default_config["site"] == "External"
    assert result.default_config["region"] == "wd5"
    assert result.base_url == "https://acme.wd5.myworkdayjobs.com/en-US/External"


def test_detect_unknown_url_returns_none() -> None:
    assert detect_source_from_url("https://example.com/careers") is None
