"""Tests for Snowflake Careers apply delegation."""

from unittest.mock import MagicMock, patch

from app.appliers import ApplyContext, get_applier
from app.appliers.types import ApplyResult
from app.schemas.profile import ApplyProfile


def test_snowflake_careers_delegates_to_ashby() -> None:
    profile = ApplyProfile(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Remote",
        resume_text="Built databases.",
        cover_letter_template="Dear team,",
    )
    ctx = ApplyContext(
        job_external_id="00898e37-87aa-47e6-9df7-aefabac4ab01",
        job_title="Senior Solution Engineer",
        company="Snowflake",
        job_url="https://jobs.ashbyhq.com/snowflake/00898e37-87aa-47e6-9df7-aefabac4ab01",
        config={"company": "Snowflake", "portal_id": "snowflake"},
        profile=profile,
        resume_file=None,
        credentials=None,
        dry_run=True,
    )

    delegated_ctx: ApplyContext | None = None

    def capture_apply(inner_ctx: ApplyContext) -> ApplyResult:
        nonlocal delegated_ctx
        delegated_ctx = inner_ctx
        return ApplyResult(status="dry_run", payload={"board": inner_ctx.config.get("board")})

    ashby = MagicMock()
    ashby.apply.side_effect = capture_apply

    with patch("app.appliers.adapters.snowflake_careers.get_applier", return_value=ashby):
        result = get_applier("snowflake_careers").apply(ctx)

    assert result.status == "dry_run"
    assert delegated_ctx is not None
    assert delegated_ctx.config["board"] == "snowflake"
    assert result.payload is not None
    assert result.payload["snowflake_careers_route"] == "ashby"
    assert result.payload["delegated_adapter"] == "ashby"
