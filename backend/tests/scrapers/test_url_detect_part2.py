"""Tests for careers-page URL detection (part 2)."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_indeed_search_url() -> None:
    result = detect_source_from_url(
        "https://www.indeed.com/jobs?q=python&l=remote",
        page_title="Python Jobs, Employment in Remote | Indeed",
    )
    assert result is not None
    assert result.adapter_key == "indeed"
    assert result.default_config["q"] == "python"
    assert result.default_config["l"] == "remote"
    assert result.suggested_name == "Python Jobs, Employment in Remote"
    assert result.query_url == "https://www.indeed.com/jobs?q=python&l=remote"


def test_detect_indeed_country_subdomain() -> None:
    result = detect_source_from_url("https://uk.indeed.com/jobs?q=engineer&l=London")
    assert result is not None
    assert result.adapter_key == "indeed"
    assert result.base_url == "https://uk.indeed.com/jobs"


def test_detect_unknown_url_returns_none() -> None:
    assert detect_source_from_url("https://example.com/careers") is None


def test_detect_non_http_scheme_returns_none() -> None:
    assert detect_source_from_url("ftp://boards.greenhouse.io/acme") is None


def test_detect_missing_netloc_returns_none() -> None:
    assert detect_source_from_url("https:///acme") is None


def test_detect_greenhouse_api_short_path_returns_none() -> None:
    assert detect_source_from_url("https://boards-api.greenhouse.io/v1/boards") is None


def test_detect_greenhouse_api_wrong_prefix_returns_none() -> None:
    assert detect_source_from_url("https://boards-api.greenhouse.io/v2/other/acme") is None


def test_detect_greenhouse_board_jobs_prefix_path() -> None:
    result = detect_source_from_url("https://boards.greenhouse.io/jobs/acme-corp")
    assert result is not None
    assert result.adapter_key == "greenhouse"
    assert result.default_config["board_token"] == "acme-corp"


def test_detect_greenhouse_board_only_jobs_segment_returns_none() -> None:
    assert detect_source_from_url("https://boards.greenhouse.io/jobs") is None


def test_detect_greenhouse_job_boards_host() -> None:
    result = detect_source_from_url("https://job-boards.greenhouse.io/acme")
    assert result is not None
    assert result.default_config["board_token"] == "acme"


def test_detect_lever_no_site_returns_none() -> None:
    assert detect_source_from_url("https://jobs.lever.co/") is None


def test_detect_ashby_posting_api_path() -> None:
    result = detect_source_from_url("https://example.com/posting-api/job-board/notion/jobs")
    assert result is not None
    assert result.adapter_key == "ashby"
    assert result.default_config["board"] == "notion"


def test_detect_ashby_posting_api_missing_board_returns_none() -> None:
    assert detect_source_from_url("https://example.com/posting-api/job-board") is None


def test_detect_ashby_no_board_returns_none() -> None:
    assert detect_source_from_url("https://jobs.ashbyhq.com/") is None


def test_detect_workday_wday_cxs_path() -> None:
    result = detect_source_from_url("https://acme.myworkdayjobs.com/wday/cxs/tenant2/External/jobs")
    assert result is not None
    assert result.adapter_key == "workday"
    assert result.default_config["tenant"] == "tenant2"
    assert result.default_config["site"] == "External"
    assert "region" not in result.default_config


def test_detect_workday_plain_host_no_locale_prefix() -> None:
    result = detect_source_from_url("https://acme.myworkdayjobs.com/External")
    assert result is not None
    assert result.default_config["tenant"] == "acme"
    assert result.default_config["site"] == "External"
    assert result.default_config["locale"] == "en-US"
    assert result.base_url == "https://acme.myworkdayjobs.com/en-US/External"


def test_detect_workday_locale_only_no_site_returns_none() -> None:
    assert detect_source_from_url("https://acme.myworkdayjobs.com/en-US/") is None


def test_detect_workday_non_workday_host_returns_none() -> None:
    assert detect_source_from_url("https://acme.example.com/External") is None


def test_detect_google_www_wrong_path_returns_none() -> None:
    assert detect_source_from_url("https://www.google.com/search?q=jobs") is None


def test_detect_google_www_no_query_params_uses_fallback_name() -> None:
    result = detect_source_from_url(
        "https://www.google.com/about/careers/applications/jobs/results/"
    )
    assert result is not None
    assert result.adapter_key == "google_careers"
    assert result.suggested_name == "Google"
    assert "q" not in result.default_config
    assert "location" not in result.default_config


def test_detect_google_blank_title_falls_back_to_parts() -> None:
    result = detect_source_from_url(
        "https://www.google.com/about/careers/applications/jobs/results/?q=software",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the name is built from parts.
    assert result.suggested_name == "Google / software"


def test_detect_google_www_bare_no_query_no_title_returns_google_careers() -> None:
    result = detect_source_from_url(
        "https://google.com/about/careers/applications/jobs/results?q=&location="
    )
    assert result is not None
    # Blank query values are stripped to empty, so name falls back to "Google".
    assert result.suggested_name == "Google"


def test_detect_indeed_non_jobs_path_returns_none() -> None:
    assert detect_source_from_url("https://www.indeed.com/companies") is None


def test_detect_indeed_no_params_no_title_uses_fallback_name() -> None:
    result = detect_source_from_url("https://www.indeed.com/jobs")
    assert result is not None
    assert result.adapter_key == "indeed"
    assert result.suggested_name == "Indeed Search"
    assert "q" not in result.default_config
    assert "l" not in result.default_config


def test_detect_indeed_keyword_only_fallback_name() -> None:
    result = detect_source_from_url("https://www.indeed.com/jobs?q=python")
    assert result is not None
    assert result.suggested_name == "Indeed: python"
    assert "l" not in result.default_config


def test_detect_indeed_blank_title_uses_parts() -> None:
    result = detect_source_from_url(
        "https://www.indeed.com/jobs?q=python&l=remote",
        page_title="   ",
    )
    assert result is not None
    # Whitespace-only title strips to empty, so the name is built from parts.
    assert result.suggested_name == "Indeed: python / remote"
