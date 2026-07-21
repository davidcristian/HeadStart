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


def test_detect_ashby_board_url_with_spaces() -> None:
    result = detect_source_from_url(
        "https://jobs.ashbyhq.com/Superhuman%20Platform%20Inc",
        page_title="Superhuman Careers",
    )
    assert result is not None
    assert result.adapter_key == "ashby"
    assert result.default_config["board"] == "Superhuman Platform Inc"
    assert result.base_url == "https://jobs.ashbyhq.com/Superhuman%20Platform%20Inc"
    assert result.suggested_name == "Superhuman"


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
    assert result.default_config["host_kind"] == "jobs"
    assert result.base_url == "https://acme.wd5.myworkdayjobs.com/en-US/External"


def test_detect_workday_myworkdaysite_recruiting_url() -> None:
    result = detect_source_from_url(
        "https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/LA/Role_R1"
    )
    assert result is not None
    assert result.adapter_key == "workday"
    assert result.default_config["tenant"] == "snapchat"
    assert result.default_config["site"] == "snap"
    assert result.default_config["region"] == "wd1"
    assert result.default_config["host_kind"] == "site"
    assert result.base_url == "https://wd1.myworkdaysite.com/recruiting/snapchat/snap"


def test_detect_workday_snap_careers_vanity() -> None:
    result = detect_source_from_url("https://careers.snap.com/jobs", page_title="Jobs - Snap Inc")
    assert result is not None
    assert result.adapter_key == "workday"
    assert result.default_config["tenant"] == "snapchat"
    assert result.default_config["site"] == "snap"
    assert result.default_config["host_kind"] == "site"
    assert result.suggested_name == "Jobs - Snap Inc"
    assert result.base_url == "https://wd1.myworkdaysite.com/recruiting/snapchat/snap"


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


def test_detect_shopify_careers_root_url() -> None:
    result = detect_source_from_url("https://www.shopify.com/careers")
    assert result is not None
    assert result.adapter_key == "shopify_careers"
    assert result.default_config["portal_id"] == "shopify"
    assert result.base_url == "https://www.shopify.com/careers"


def test_detect_shopify_careers_search_query() -> None:
    result = detect_source_from_url("https://www.shopify.com/careers?q=engineer")
    assert result is not None
    assert result.default_config["q"] == "engineer"
    assert result.suggested_name == "Shopify / engineer"


def test_detect_shopify_careers_page_title() -> None:
    result = detect_source_from_url(
        "https://www.shopify.com/careers",
        page_title="Engineering Careers | Shopify",
    )
    assert result is not None
    assert result.suggested_name == "Engineering"


def test_detect_shopify_non_careers_path_returns_none() -> None:
    assert detect_source_from_url("https://www.shopify.com/about") is None


def test_detect_shopify_careers_job_detail_returns_none() -> None:
    assert (
        detect_source_from_url(
            "https://www.shopify.com/careers/workplace-technology-manager_f12820dc-3c96-4815-b4d2-506d680d034f"
        )
        is None
    )


def test_detect_uber_careers_root_url() -> None:
    result = detect_source_from_url("https://www.uber.com/us/en/careers/list/")
    assert result is not None
    assert result.adapter_key == "uber_careers"
    assert result.default_config["portal_id"] == "uber"
    assert result.default_config["careers_locale_path"] == "us/en"
    assert result.base_url == "https://www.uber.com/us/en/careers/list/"


def test_detect_uber_careers_job_detail_returns_none() -> None:
    assert detect_source_from_url("https://www.uber.com/us/en/careers/list/154672") is None


def test_detect_snowflake_careers_search_url() -> None:
    result = detect_source_from_url("https://careers.snowflake.com/us/en/search-results")
    assert result is not None
    assert result.adapter_key == "snowflake_careers"
    assert result.default_config["portal_id"] == "snowflake"
    assert result.default_config["board"] == "snowflake"
    assert result.base_url == "https://careers.snowflake.com/us/en/search-results"


def test_detect_snowflake_careers_search_query() -> None:
    result = detect_source_from_url("https://careers.snowflake.com/us/en/search-results?q=engineer")
    assert result is not None
    assert result.default_config["q"] == "engineer"
    assert result.suggested_name == "Snowflake / engineer"


def test_detect_snowflake_careers_job_detail_returns_none() -> None:
    assert (
        detect_source_from_url("https://careers.snowflake.com/us/en/job/senior-engineer/12345")
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
    result = detect_source_from_url("https://api.ashbyhq.com/posting-api/job-board/notion/jobs")
    assert result is not None
    assert result.adapter_key == "ashby"
    assert result.default_config["board"] == "notion"


def test_detect_ashby_posting_api_missing_board_returns_none() -> None:
    assert detect_source_from_url("https://api.ashbyhq.com/posting-api/job-board") is None


def test_detect_ashby_rejects_non_ashby_host_with_api_path() -> None:
    """Path substring alone must not label arbitrary hosts as Ashby."""
    assert detect_source_from_url("https://evil.example.com/posting-api/job-board/acme") is None
    assert detect_source_from_url("https://example.com/posting-api/job-board/notion/jobs") is None
    assert detect_source_from_url("https://evilashbyhq.com/posting-api/job-board/acme") is None


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
