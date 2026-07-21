"""Tests for Workday tenant/site/job resolution."""

import pytest

from app.appliers.adapters import workday_target
from app.appliers.adapters.workday_target import (
    _from_job_url,
    resolve_job_path,
    resolve_job_posting_id,
    resolve_target,
)


def test_resolve_target_from_config_builds_host_with_region() -> None:
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "region": "wd5"}, "")
    assert target is not None
    assert target.host == "acme.wd5.myworkdayjobs.com"
    assert target.region == "wd5"
    assert target.company == "acme"
    assert target.api_base() == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme"


def test_resolve_target_from_config_without_region() -> None:
    target = resolve_target({"tenant": "acme", "site": "AcmeCareers", "company": "ACME"}, "")
    assert target is not None
    assert target.host == "acme.myworkdayjobs.com"
    assert target.region is None
    assert target.company == "ACME"


def test_resolve_target_returns_none_without_tenant_or_site() -> None:
    assert resolve_target({"tenant": "acme"}, "") is None
    assert resolve_target({"site": "AcmeCareers"}, "") is None
    assert resolve_target({}, "") is None


def test_resolve_target_from_url_without_region() -> None:
    target = resolve_target(
        {},
        "https://acme.myworkdayjobs.com/en-US/AcmeCareers/job/US-CA/Role_JR1",
    )
    assert target is not None
    assert target.tenant == "acme"
    assert target.region is None
    assert target.site == "AcmeCareers"
    assert target.locale == "en-US"


def test_resolve_target_from_url_without_locale_prefix() -> None:
    target = resolve_target(
        {},
        "https://acme.wd5.myworkdayjobs.com/AcmeCareers/job/US-CA/Role_JR1",
    )
    assert target is not None
    assert target.site == "AcmeCareers"
    assert target.locale == "en-US"


def test_resolve_target_returns_none_for_non_workday_host() -> None:
    assert resolve_target({}, "https://example.com/careers/job/1") is None


def test_resolve_target_returns_none_when_url_has_no_site_segment() -> None:
    assert resolve_target({}, "https://acme.wd5.myworkdayjobs.com/en-US") is None


def test_resolve_job_path_from_config_strips_slashes() -> None:
    assert resolve_job_path({"job_path": "/US-CA/Role_JR1/"}, "") == "US-CA/Role_JR1"


def test_resolve_job_path_returns_none_without_url_or_config() -> None:
    assert resolve_job_path({}, "") is None


def test_resolve_job_path_returns_none_when_url_lacks_job_segment() -> None:
    assert resolve_job_path({}, "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers") is None


def test_resolve_job_posting_id_from_config() -> None:
    assert resolve_job_posting_id({"job_posting_id": "posting-1"}, "", "") == "posting-1"


def test_resolve_job_posting_id_from_external_id_with_underscore() -> None:
    assert resolve_job_posting_id({}, "", "Role_JR1") == "Role_JR1"


def test_resolve_job_posting_id_from_plain_external_id() -> None:
    assert resolve_job_posting_id({}, "", "JR1") == "JR1"


def test_from_job_url_raises_when_tenant_is_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        workday_target,
        "board_from_url",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("tenant")),
    )
    with pytest.raises(ValueError, match="tenant"):
        _from_job_url(
            "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers/job/US-CA/Role_JR1",
            company="",
            locale="en-US",
        )


def test_resolve_target_site_without_region_returns_none() -> None:
    assert (
        resolve_target(
            {"tenant": "snapchat", "site": "snap", "host_kind": "site"},
            "",
        )
        is None
    )


def test_resolve_target_from_myworkdaysite_job_url() -> None:
    target = resolve_target(
        {"company": "Snap"},
        "https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/"
        "Los-Angeles-California/Role_R1",
    )
    assert target is not None
    assert target.tenant == "snapchat"
    assert target.site == "snap"
    assert target.region == "wd1"
    assert target.host_kind == "site"
    assert target.host == "wd1.myworkdaysite.com"
    assert target.board_url == "https://wd1.myworkdaysite.com/recruiting/snapchat/snap"
    assert (
        target.job_page_url("Los-Angeles-California/Role_R1")
        == "https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/"
        "Los-Angeles-California/Role_R1"
    )


def test_resolve_job_path_from_myworkdaysite_url() -> None:
    path = resolve_job_path(
        {},
        "https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/"
        "Los-Angeles-California/Role_R1",
    )
    assert path == "Los-Angeles-California/Role_R1"


def test_resolve_target_site_host_kind_from_config() -> None:
    target = resolve_target(
        {
            "tenant": "snapchat",
            "site": "snap",
            "region": "wd1",
            "host_kind": "site",
            "company": "Snap",
        },
        "",
    )
    assert target is not None
    assert target.host == "wd1.myworkdaysite.com"
    assert target.api_base() == "https://wd1.myworkdaysite.com/wday/cxs/snapchat"
