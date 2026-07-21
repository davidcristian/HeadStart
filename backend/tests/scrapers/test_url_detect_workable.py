"""URL detection tests for the Workable careers scraper."""

from app.scrapers.url_detect import detect_source_from_url


def test_detect_workable_ignores_unrelated_host() -> None:
    assert detect_source_from_url("https://careers.example.com/jobs") is None


def test_detect_workable_account_url() -> None:
    result = detect_source_from_url("https://apply.workable.com/huggingface/")
    assert result is not None
    assert result.adapter_key == "workable"
    assert result.base_url == "https://apply.workable.com/huggingface"
    assert result.default_config["account"] == "huggingface"
    assert result.default_config["company"] == "Huggingface"


def test_detect_workable_widget_api_url() -> None:
    result = detect_source_from_url("https://apply.workable.com/api/v1/widget/accounts/huggingface")
    assert result is not None
    assert result.adapter_key == "workable"
    assert result.default_config["account"] == "huggingface"
    assert result.base_url == "https://apply.workable.com/huggingface"


def test_detect_workable_rejects_job_shortlink_and_invalid_slug() -> None:
    assert detect_source_from_url("https://apply.workable.com/j/97904BAC90") is None
    assert detect_source_from_url("https://apply.workable.com/evil.account/") is None
    assert detect_source_from_url("https://apply.workable.com/-bad/") is None
    assert detect_source_from_url("https://apply.workable.com/api/v1/widget/accounts/") is None
    assert (
        detect_source_from_url("https://apply.workable.com/api/v1/widget/accounts/evil.account")
        is None
    )


def test_detect_workable_uses_page_title() -> None:
    result = detect_source_from_url(
        "https://apply.workable.com/huggingface/",
        page_title="Hugging Face Careers",
    )
    assert result is not None
    assert result.suggested_name == "Hugging Face"


def test_detect_workable_page_title_without_suffix() -> None:
    result = detect_source_from_url(
        "https://apply.workable.com/acme/",
        page_title="Acme Corp",
    )
    assert result is not None
    assert result.suggested_name == "Acme Corp"
