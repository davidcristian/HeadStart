"""Tests for Shopify Careers apply delegation."""

from unittest.mock import MagicMock, patch

from app.appliers import ApplyContext, get_applier
from app.appliers.types import ApplyResult
from app.schemas.profile import ApplyProfile


def test_shopify_careers_delegates_to_ashby() -> None:
    profile = ApplyProfile(
        full_name="Ada Lovelace",
        email="ada@example.com",
        phone="+1 555 0100",
        location="Remote",
        resume_text="Built databases.",
        cover_letter_template="Dear team,",
    )
    ctx = ApplyContext(
        job_external_id="7a204574-fb6c-4b27-84f3-d2a693739b18",
        job_title="Account Executive",
        company="Shopify",
        job_url="https://www.shopify.com/careers?ashby_jid=7a204574-fb6c-4b27-84f3-d2a693739b18",
        config={"company": "Shopify", "portal_id": "shopify"},
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

    with patch("app.appliers.adapters.shopify_careers.get_applier", return_value=ashby):
        result = get_applier("shopify_careers").apply(ctx)

    assert result.status == "dry_run"
    assert delegated_ctx is not None
    assert delegated_ctx.config["board"] == "shopify"
    assert result.payload is not None
    assert result.payload["shopify_careers_route"] == "ashby"
    assert result.payload["delegated_adapter"] == "ashby"


def test_has_applier_registers_shopify_careers() -> None:
    from app.appliers.base import has_applier

    assert has_applier("shopify_careers")
