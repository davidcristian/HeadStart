# Billing, plans, promo codes, admin

This area covers Stripe checkout and subscription webhooks (`services/billing.py`), promo-code creation/validation/redemption (`services/promo_codes.py`), plan gating and limits (`core/plans.py`, `services/plan_limits.py`), and the admin user/data-request management surface (`services/admin.py`, `api/v1/admin.py`). The audit found no critical or high-severity defects, but a cluster of medium/low correctness issues in the Stripe webhook path (no idempotency or event-ordering guard, so stale/out-of-order events can re-grant or wipe a plan), a promo-code brute-force rate limiter that is bypassable through the checkout entry point, several plan-gate and admin/Stripe desync gaps, plus dead code and doc drift.

**Summary:** critical 0 · high 0 · medium 3 · low 8 (14 confirmed records; 3 merge pairs collapsed).

---

<a id="bil-01"></a>
### BIL-01 — Admin user mutations (deactivate, grant admin, plan change) write no audit record
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/34)) · Confidence: high (3/3 verifiers) · Effort: M · WS19

**Update (2026-07-10).** Fixed: `AdminService.update_user` snapshots before/after `is_active` / `is_admin` / `plan` and emits a structured `admin_event=user_update` INFO line (`actor_id`, `target_id`, changed fields only) via `app.core.admin_events`. No-op patches do not log.

**Locations:** `backend/app/services/admin.py:26` (`AdminService.update_user`).

**Evidence.** `update_user` changes `is_active`, `is_admin`, and `plan` via `users.update_flags` but emits no log line and writes no audit row — there is no `logging` import in `admin.py`, and `DataRequestLog` covers only export/delete flows, not privilege or plan changes. Privilege escalation or account lockout therefore leaves zero server-side trail.

**Failure scenario.** A compromised or rogue admin promotes an account to admin or deactivates users; no record of who did what and when exists, so the action is undetectable during incident response.

**Suggested fix.** Emit a structured audit entry (actor_id, target_id, before/after flags) to a log and/or a dedicated admin-action audit table on every `update_user` change.

**Verification.** Confirmed 3/3 adversarial verifiers. Genuine observability gap but pure defense-in-depth with no exploit path; graded at the low end of medium.

<a id="bil-02"></a>
### BIL-02 — subscription.updated applied unconditionally; stale/out-of-order event re-grants plan
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: M · WS22

**Locations:** `backend/app/services/billing.py:202` (`_on_subscription_updated`); plus `backend/app/services/billing.py:162`, `backend/app/services/billing.py:218`.

**Evidence.** `handle_webhook` performs no event-id dedup or ordering check, and `_on_subscription_updated` overwrites `subscription_status`/`plan` from whatever event arrives. Stripe does not guarantee delivery ordering, and `construct_event` verifies only the signature and timestamp tolerance — it does not prevent replay. This finding pairs with BIL-03, which covers the delete handler; both stem from the same missing ordering guard.

**Failure scenario.** `customer.subscription.deleted` downgrades a user to free, then a delayed or replayed `customer.subscription.updated` (status=active) arrives and silently re-grants the paid plan after cancellation.

**Suggested fix.** Persist the last-processed event id/created-timestamp per subscription (or a processed-event table), ignore events older than the current state, and treat `deleted` as terminal.

**Verification.** Confirmed 3/3 adversarial verifiers. Verified `handle_webhook` has no dedup/ordering guard and `_on_subscription_updated` unconditionally overwrites status/plan; a replayed/late `updated` after cancellation re-grants a paid plan. Recoverable but real; medium is fair.

<a id="bil-03"></a>
### BIL-03 — Subscription webhook applies stale/out-of-order events (deleted for old sub wipes plan)
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS22

**Locations:** `backend/app/services/billing.py:218` (`_on_subscription_deleted`); plus `backend/app/services/billing.py:202`.

**Evidence.** `_on_subscription_deleted` unconditionally sets `plan='free'`/`status='canceled'` without comparing `subscription.get('id')` to `user.stripe_subscription_id`; `_on_subscription_updated` (L202) likewise overwrites id/status/plan from any incoming event. Stripe provides no ordering guarantee. This is the delete-handler counterpart to BIL-02; the fix here (id matching) is narrower and complements the ordering/dedup fix there.

**Failure scenario.** A user cancels subscription A then buys subscription B (active). A late `customer.subscription.deleted` for sub A downgrades the paying user to free; a late `updated` for a superseded sub regresses status/plan.

**Suggested fix.** Apply `deleted`/`updated` only when the event's subscription id matches the user's current `stripe_subscription_id`; ignore events for superseded subscriptions.

**Verification.** Confirmed 3/3 adversarial verifiers. Verified `_on_subscription_deleted` (L218) sets `plan='free'` without comparing the subscription id to `user.stripe_subscription_id`; a late deleted for a superseded sub wipes a paying user's plan. No upstream ordering guard; medium is fair.

<a id="bil-04"></a>
### BIL-04 — GET /admin/data-requests `limit` has no lower bound; negative reaches SQL LIMIT
⚪ **LOW** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/107)) · Confidence: medium (5/5 verifiers) · Effort: XS · WS22

**Locations:** `backend/app/api/v1/admin.py:47` (`list_data_requests`); reaches the query at `backend/app/repositories/data_request_logs.py:22`. Merged from two identical records (uid 46 and uid 301) reporting the same defect.

**Evidence.** `limit: int = 100` is a bare parameter clamped only on the upper end via `list_data_requests(limit=min(limit, 500))`; there is no `ge=` guard, so `min(-5, 500) == -5` flows to `select(...).limit(-5)`. Other list routers in the codebase use `Query(ge=1, le=...)`. Postgres rejects a negative `LIMIT`; the SQLite test DB treats it as no-limit (returns all rows), masking the defect and keeping coverage green.

```python
limit: int = 100
...
return await service.list_data_requests(limit=min(limit, 500))
```

**Failure scenario.** An admin calling `GET /admin/data-requests?limit=-1` triggers a 500 on Postgres (negative LIMIT), while SQLite silently returns every row — a bounds gap hidden by the test backend.

**Suggested fix.** Use `Query(default=100, ge=1, le=500)` to bound both ends, matching the other list routes.

**Verification.** Confirmed 5/5 adversarial verifiers (aggregated across the two merged records). Admin-only, low-sensitivity; low is fair.

<a id="bil-06"></a>
### BIL-06 — scraper_allowed defaults unknown adapters to allowed on every plan (fail-open)
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS22

**Locations:** `backend/app/core/plans.py:112` (`scraper_allowed`).

**Evidence.** Any `adapter_key` not present in `FREE_SCRAPERS` or `PREMIUM_SCRAPERS` returns `True` for all plans (the comment reads "Unknown adapters default to allowed"). A new premium scraper added to the registry but not to `PREMIUM_SCRAPERS` is therefore silently free on every plan.

**Failure scenario.** A newly registered paid scraper that a developer forgets to add to `PREMIUM_SCRAPERS` becomes usable by Free users on every source, undercutting monetization until someone notices.

**Suggested fix.** Fail closed for unknown paid adapters, or add a test asserting that every registered scraper is classified into `FREE_SCRAPERS` or `PREMIUM_SCRAPERS`.

**Verification.** Confirmed 3/3 adversarial verifiers. Fail-open behavior confirmed at L112-113, but it requires a developer omission to trigger; defense-in-depth, low is fair.

<a id="bil-07"></a>
### BIL-07 — plans.py comment says 'Pro unlocks the rest' but premium scrapers are Plus+
⚪ **LOW** · 📝 doc · Status: ✅ done · Confidence: certain (5/5 verifiers) · Effort: XS · WS22

**Locations:** `backend/app/core/plans.py:16` (`FREE_SCRAPERS` / `scraper_allowed`); plus `backend/app/core/plans.py:111`.

**Evidence.** The L16 comment reads "Scrapers included on Free (...). Pro unlocks the rest," but `scraper_allowed` (L111) returns `plan in ('plus', 'pro')` for `PREMIUM_SCRAPERS`. ADR 0010 (line 45), `auth.md:168`, and `pricing.ts:138` all confirm that indeed/linkedin/playwright are Plus+, not Pro-only.

**Failure scenario.** A developer reading the inline comment believes premium scrapers are Pro-exclusive and "fixes" the gate to `plan == 'pro'`, wrongly revoking access for paying Plus users.

**Suggested fix.** Reword the comment to "Plus+ unlocks the premium scrapers" to match `scraper_allowed` / ADR 0010.

**Resolution.** Comment rewritten to "Plus+ unlocks PREMIUM_SCRAPERS" in the BIL-06 change; `docs/modules/billing.md` now states premium scrapers are Plus+ (webhook remains Pro-only). Gate tests already assert Plus unlocks `indeed`/`linkedin`/`playwright`.

**Verification.** Confirmed 5/5 adversarial verifiers. Real but harmless doc drift.

<a id="bil-08"></a>
### BIL-08 — Admin plan change ignores active Stripe subscription; webhook overwrites it
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: M · WS22

**Locations:** `backend/app/services/admin.py:38` (`update_user`); plus `backend/app/services/billing.py:202`.

**Evidence.** `update_user` writes `data.plan` directly to `user.plan` with no check for `user.stripe_subscription_id`/`subscription_status`. The `plan` field is authoritative for gating but is also driven by `_on_subscription_updated`, so the two can disagree.

**Failure scenario.** An admin downgrades a paying user via `PATCH /admin/users/{id}`; the next `subscription.updated` webhook reverts `plan` to the Stripe value, so the admin change silently doesn't stick or leaves plan/billing mismatched.

**Suggested fix.** Warn or block plan edits for users with an active Stripe subscription, or reconcile via Stripe (cancel/modify) rather than only mutating `user.plan`.

**Verification.** Confirmed 3/3 adversarial verifiers. Admin-only and recoverable; low is fair.

**Resolution.** `AdminService.update_user` rejects a plan change when
`subscription_status` still grants access (`active` / `trialing` / `past_due`)
via `subscription_grants_plan`, matching checkout's "already subscribed" gate.
Same-plan no-ops and non-plan flag edits remain allowed; canceled (and other
non-granting) statuses still permit manual overrides.
Shipped in [PR #110](https://github.com/davidcristian/HeadStart/pull/110).

<a id="bil-09"></a>
### BIL-09 — Promo brute-force rate limit bypassed via /billing/checkout (resolve_for_checkout unthrottled)
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/111)) · Confidence: high (3/3 verifiers) · Effort: S · WS22

**Locations:** `backend/app/services/promo_codes.py:108` (`PromoCodeService.resolve_for_checkout`); plus `backend/app/services/promo_codes.py:95`, `backend/app/services/promo_codes.py:209`, `backend/app/services/billing.py:79`. Merged from two records (uid 22 and uid 27) describing the same bypass from the checkout and promo-service sides.

**Evidence.** `validate_for_user` enforces `_MAX_VALIDATION_ATTEMPTS` (10 per 15 min) via `_enforce_validation_rate_limit` + `record_validation_attempt`. `resolve_for_checkout` — invoked by `POST /billing/checkout` through `create_checkout_session` (billing.py:79) — calls `get_by_code` + `_assert_redeemable` with no rate limit and no attempt logging, and invalid codes raise before any Stripe call. No global rate limiter exists to backstop this.

**Failure scenario.** An attacker who has hit the 10/15min cap on `/promo/validate` submits guessed `promo_code` values through `POST /billing/checkout` instead, distinguishing valid from invalid by the error and enumerating discount codes with no throttle.

**Suggested fix.** Route checkout promo resolution through the same attempt-record + rate-limit guard (or a shared guard) so all promo-code entry points are throttled.

**Verification.** Confirmed 3/3 adversarial verifiers (both merged records agreed). Auth-gated code enumeration with no direct money loss; correctly graded low, not medium.

<a id="bil-10"></a>
### BIL-10 — Free-trial gate keys on requested plan, not the plan_upgrade target billed
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: XS · WS22

**Locations:** `backend/app/services/billing.py:121` (`create_checkout_session`).

**Evidence.** `checkout_plan` is recomputed from `promo.plan_target` (L84) so the line item and the grant use the target plan, but the trial gate stays `plan == 'pro'` on the original requested plan (L121) rather than `checkout_plan`.

**Failure scenario.** A `plan_upgrade` promo with `plan_target='pro'` on a requested `starter` checkout grants Pro with no trial; conversely, a requested `pro` checkout upgraded to a non-pro target still attaches the Pro trial.

**Suggested fix.** Gate the trial on `checkout_plan` (the plan actually billed/granted) rather than the requested plan.

**Verification.** Confirmed 3/3 adversarial verifiers. Real logic drift; low.

**Resolution.** `create_checkout_session` now gates `STRIPE_TRIAL_DAYS` on `checkout_plan == "pro"` (after `plan_upgrade`), not the client-requested plan. Regression covers upgrade-to-Pro (trial attached) and upgrade-away-from-Pro (no default trial). Shipped in [PR #112](https://github.com/davidcristian/HeadStart/pull/112).

<a id="bil-11"></a>
### BIL-11 — snapshot() plan field uses a no-op ternary (both branches identical)
⚪ **LOW** · ♻️ refactor · Status: ✅ done · Confidence: certain (3/3 verifiers) · Effort: XS · WS22

**Locations:** `backend/app/services/plan_limits.py:68` (`PlanLimitsService.snapshot`). Merged from two identical records (uid 25 and uid 31) reporting the same dead ternary.

**Evidence.** The field is literally `"plan": user.plan if not user.is_admin else user.plan` — both branches return `user.plan`, so the condition is dead. It likely lost an intent to expose an effective vs. raw plan (admins report the raw stored plan while `effective_plan` is pro), but it currently collapses to the raw plan.

**Failure scenario.** No runtime impact, but the dead ternary reads as if the admin plan is special-cased when it is not, risking a wrong edit later and obscuring the plan vs. `effective_plan` split.

**Suggested fix.** Replace with plain `user.plan` (or implement the intended `effective_plan` value) and drop the redundant conditional.

**Verification.** Confirmed 3/3 adversarial verifiers (both merged records verified the line verbatim). Cosmetic refactor; low.

<a id="bil-13"></a>
### BIL-13 — Stripe PromotionCode metadata promo_code_id always empty (set before flush)
⚪ **LOW** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: S · WS22

**Locations:** `backend/app/services/promo_codes.py:245` (`_create_stripe_objects`); plus `backend/app/services/promo_codes.py:78`, `backend/app/services/promo_codes.py:82`.

**Evidence.** `create_code` calls `_create_stripe_objects` (L78) *before* `self.promos.add(promo)` (L82) flushes and assigns `promo.id`. Because `promo.id` is a no-default autoincrement PK, the metadata `{"promo_code_id": str(promo.id or "")}` at L245 always evaluates to `""` — the Stripe promotion code is never tagged with the local id.

**Failure scenario.** Every Stripe promotion code is created with `promo_code_id=""`; any future reconciliation or back-mapping from a Stripe promotion to the local promo by metadata silently fails or mis-maps.

**Suggested fix.** Flush the promo row (assign id) before creating Stripe objects, or call `PromotionCode.modify` to set the metadata after `add`.

**Verification.** Confirmed 3/3 adversarial verifiers. Low data-quality bug.
