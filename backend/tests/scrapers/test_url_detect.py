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


def test_detect_smartrecruiters_careers_board_url() -> None:
    result = detect_source_from_url(
        "https://careers.smartrecruiters.com/Atlassian",
        page_title="Atlassian Careers",
    )
    assert result is not None
    assert result.adapter_key == "smartrecruiters"
    assert result.default_config["company_id"] == "Atlassian"
    assert result.suggested_name == "Atlassian"
    assert result.base_url == "https://careers.smartrecruiters.com/Atlassian"


def test_detect_smartrecruiters_api_url() -> None:
    result = detect_source_from_url(
        "https://api.smartrecruiters.com/v1/companies/AcmeCorp/postings?limit=100"
    )
    assert result is not None
    assert result.adapter_key == "smartrecruiters"
    assert result.default_config["company_id"] == "AcmeCorp"


def test_detect_workday_board_url() -> None:
    result = detect_source_from_url("https://acme.wd5.myworkdayjobs.com/en-US/External/jobs/123")
    assert result is not None
    assert result.adapter_key == "workday"
    assert result.default_config["tenant"] == "acme"
    assert result.default_config["site"] == "External"
    assert result.default_config["region"] == "wd5"
    assert result.base_url == "https://acme.wd5.myworkdayjobs.com/en-US/External"


def test_detect_google_careers_search_url() -> None:
    result = detect_source_from_url(
        "https://www.google.com/about/careers/applications/jobs/results/?q=software&location=United+States",
        page_title="Search Jobs — Google Careers",
    )
    assert result is not None
    assert result.adapter_key == "google_careers"
    assert result.default_config["company"] == "Google"
    assert result.default_config["q"] == "software"
    assert result.default_config["location"] == "United States"
    assert result.suggested_name == "Search Jobs"


def test_detect_google_careers_root_url() -> None:
    result = detect_source_from_url("https://careers.google.com/")
    assert result is not None
    assert result.adapter_key == "google_careers"
    assert result.default_config["portal_id"] == "google"


def test_detect_microsoft_careers_board_url() -> None:
    result = detect_source_from_url(
        "https://apply.careers.microsoft.com/careers?q=software&location=Redmond",
        page_title="Search Jobs — Microsoft Careers",
    )
    assert result is not None
    assert result.adapter_key == "microsoft_careers"
    assert result.default_config["company"] == "Microsoft"
    assert result.default_config["q"] == "software"
    assert result.default_config["location"] == "Redmond"
    assert result.suggested_name == "Search Jobs"
    assert result.base_url == "https://apply.careers.microsoft.com/careers"


def test_detect_microsoft_careers_api_url() -> None:
    result = detect_source_from_url(
        "https://apply.careers.microsoft.com/api/pcsx/search?domain=microsoft.com&query=kernel"
    )
    assert result is not None
    assert result.adapter_key == "microsoft_careers"
    assert result.default_config["q"] == "kernel"


def test_detect_amazon_jobs_search_url() -> None:
    result = detect_source_from_url(
        "https://www.amazon.jobs/en/search?base_query=software&loc_query=Seattle",
        page_title="Software Jobs | Amazon.jobs",
    )
    assert result is not None
    assert result.adapter_key == "amazon_jobs"
    assert result.default_config["company"] == "Amazon"
    assert result.default_config["base_query"] == "software"
    assert result.default_config["loc_query"] == "Seattle"
    assert result.default_config["locale"] == "en"
    assert result.suggested_name == "Software"
    assert result.base_url == "https://www.amazon.jobs/en/search"


def test_detect_amazon_jobs_api_url() -> None:
    result = detect_source_from_url(
        "https://www.amazon.jobs/en/search.json?base_query=kernel&country=USA"
    )
    assert result is not None
    assert result.adapter_key == "amazon_jobs"
    assert result.default_config["base_query"] == "kernel"
    assert result.default_config["country"] == "USA"


def test_detect_meta_careers_search_url() -> None:
    result = detect_source_from_url(
        "https://www.metacareers.com/jobsearch/?q=software",
        page_title="Meta Careers",
    )
    assert result is not None
    assert result.adapter_key == "meta_careers"
    assert result.default_config["company"] == "Meta"
    assert result.default_config["q"] == "software"
    assert result.default_config["portal_id"] == "meta"
    assert result.suggested_name == "Meta"
    assert result.base_url == "https://www.metacareers.com/jobsearch/"


def test_detect_apple_careers_search_url() -> None:
    result = detect_source_from_url(
        "https://jobs.apple.com/en-us/search?search=software+engineer&location=united-states-USA",
        page_title="Search Jobs — Apple Careers",
    )
    assert result is not None
    assert result.adapter_key == "apple_careers"
    assert result.default_config["company"] == "Apple"
    assert result.default_config["search"] == "software engineer"
    assert result.default_config["location"] == "united-states-USA"
    assert result.default_config["portal_id"] == "apple"
    assert result.default_config["locale"] == "en-us"
    assert result.suggested_name == "Search Jobs"
    assert result.base_url == "https://jobs.apple.com/en-us/search"


def test_detect_apple_careers_root_search_url() -> None:
    result = detect_source_from_url("https://jobs.apple.com/en-gb/search")
    assert result is not None
    assert result.adapter_key == "apple_careers"
    assert result.default_config["locale"] == "en-gb"


def test_detect_apple_careers_job_detail_returns_none() -> None:
    assert (
        detect_source_from_url(
            "https://jobs.apple.com/en-us/details/200670239-0836/ml-research-engineer?team=MLAI"
        )
        is None
    )


def test_detect_meta_careers_root_url() -> None:
    result = detect_source_from_url("https://www.metacareers.com/jobs")
    assert result is not None
    assert result.adapter_key == "meta_careers"
    assert result.default_config["portal_id"] == "meta"


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
