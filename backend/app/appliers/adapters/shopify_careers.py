"""Shopify Careers apply adapter — delegates to Ashby."""

from __future__ import annotations

from app.appliers.base import Applier, get_applier, register_applier
from app.appliers.types import ApplyContext, ApplyResult

_DEFAULT_BOARD = "shopify"


@register_applier("shopify_careers")
class ShopifyCareersApplier(Applier):
    """Submit applications to Shopify's Ashby-backed careers board."""

    def apply(self, ctx: ApplyContext) -> ApplyResult:
        board = str(ctx.config.get("board") or _DEFAULT_BOARD)
        merged_config = {**ctx.config, "board": board}
        delegated = ApplyContext(
            job_external_id=ctx.job_external_id,
            job_title=ctx.job_title,
            company=ctx.company,
            job_url=ctx.job_url,
            config=merged_config,
            profile=ctx.profile,
            resume_file=ctx.resume_file,
            credentials=ctx.credentials,
            cover_letter=ctx.cover_letter,
            dry_run=ctx.dry_run,
        )
        result = get_applier("ashby", http=self.http).apply(delegated)
        if result.payload is None:
            return result
        payload = dict(result.payload)
        payload["shopify_careers_route"] = "ashby"
        payload["delegated_adapter"] = "ashby"
        return result.model_copy(update={"payload": payload})
