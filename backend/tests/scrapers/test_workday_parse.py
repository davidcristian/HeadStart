"""Unit tests for Workday host/path helpers."""

import pytest

from app.scrapers.adapters.workday_parse import (
    HOST_KIND_JOBS,
    HOST_KIND_SITE,
    board_from_url,
    build_host,
    extract_job_path,
    normalize_host_kind,
    parse_host,
    try_parse_host,
)


def test_normalize_host_kind_aliases() -> None:
    assert normalize_host_kind(None) == HOST_KIND_JOBS
    assert normalize_host_kind("JOBS") == HOST_KIND_JOBS
    assert normalize_host_kind("site") == HOST_KIND_SITE
    assert normalize_host_kind("myworkdaysite") == HOST_KIND_SITE


def test_parse_host_variants() -> None:
    assert parse_host("acme.wd5.myworkdayjobs.com") == ("acme", "wd5", HOST_KIND_JOBS)
    assert parse_host("acme.myworkdayjobs.com") == ("acme", None, HOST_KIND_JOBS)
    assert parse_host("wd1.myworkdaysite.com") == ("", "wd1", HOST_KIND_SITE)
    with pytest.raises(ValueError, match="myworkdayjobs.com or \\*\\.myworkdaysite.com"):
        parse_host("example.com")
    assert try_parse_host("example.com") is None


def test_build_host_site_requires_region() -> None:
    assert build_host("acme", "wd5") == "acme.wd5.myworkdayjobs.com"
    assert build_host("acme", None) == "acme.myworkdayjobs.com"
    assert build_host("snapchat", "wd1", HOST_KIND_SITE) == "wd1.myworkdaysite.com"
    with pytest.raises(ValueError, match="require config.region"):
        build_host("snapchat", None, HOST_KIND_SITE)


def test_board_from_url_site_and_cxs() -> None:
    site = board_from_url("https://wd1.myworkdaysite.com/recruiting/snapchat/snap")
    assert site.host_kind == HOST_KIND_SITE
    assert site.api_url == "https://wd1.myworkdaysite.com/wday/cxs/snapchat/snap/jobs"
    assert site.job_url("/job/LA/R1").endswith("/recruiting/snapchat/snap/job/LA/R1")
    assert site.job_url("job/LA/R1").endswith("/recruiting/snapchat/snap/job/LA/R1")
    assert site.job_url("") == site.board_url

    cxs = board_from_url("https://wd1.myworkdaysite.com/wday/cxs/snapchat/snap/jobs")
    assert cxs.tenant == "snapchat"
    assert cxs.site == "snap"


def test_board_from_url_site_missing_recruiting_raises() -> None:
    with pytest.raises(ValueError, match="/recruiting/"):
        board_from_url("https://wd1.myworkdaysite.com/en-US/snap")


def test_board_from_url_cxs_missing_segments_raises() -> None:
    with pytest.raises(ValueError, match="missing tenant or site"):
        board_from_url("https://wd1.myworkdaysite.com/wday/cxs/snapchat")


def test_board_from_url_site_empty_tenant_raises() -> None:
    with pytest.raises(ValueError, match="missing tenant or site"):
        board_from_url("https://wd1.myworkdaysite.com/recruiting//snap")


def test_board_from_url_jobs_relative_and_empty_job_url() -> None:
    board = board_from_url("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers")
    assert board.job_url("") == board.board_url
    assert board.job_url("relative/path").endswith("/AcmeCareers/relative/path")
    assert board.api_base.endswith("/wday/cxs/acme")


def test_extract_job_path_empty_job_segment() -> None:
    assert extract_job_path("https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/") is None
    assert extract_job_path("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/job/") is None


def test_board_from_url_cxs_empty_tenant_on_jobs_host() -> None:
    with pytest.raises(ValueError, match="missing tenant or site"):
        board_from_url("https://acme.wd5.myworkdayjobs.com/wday/cxs//External/jobs")
    assert (
        extract_job_path("https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/LA/Role_R1")
        == "LA/Role_R1"
    )
    assert (
        extract_job_path("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/job/LA/Role_R1")
        == "LA/Role_R1"
    )
    assert extract_job_path("https://example.com/job/x") is None
    assert extract_job_path("https://wd1.myworkdaysite.com/recruiting/snapchat/snap") is None
    assert extract_job_path("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers") is None
