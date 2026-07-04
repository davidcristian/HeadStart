# Services — discovery, apply pipeline, alerts, digest

This area covers the backend business-logic layer (`backend/app/services/`): the scrape/notify pipeline, the live- and auto-apply flows, digest batching and flushing, ghost-detection, application alerts, compensation parsing, and RSS rendering. The audit's headline is that the worker-driven pipeline services lack the concurrency and before-commit discipline the rest of the codebase applies elsewhere: the apply path has a non-atomic double-submit guard and no auto-apply volume ceiling, and both the digest and ghost-detection batch loops run every user's work in a single transaction with no per-item isolation, so one bad target or token error rolls back or re-sends others' work. A cluster of lower-severity correctness gaps in compensation parsing, currency display, alert fan-out, and RSS sanitization round out the findings.

**Summary:** critical 0 · high 0 · medium 6 · low 8 (14 findings from 16 records after merging two duplicate pairs).

---

<a id="svc-01"></a>
### SVC-01 — Live-apply double-submit guard is non-atomic, no unique constraint or lock
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done · Confidence: high (3/3 verifiers) · Effort: M · WS14

> Merged with **SVC-03** ("Double-submit guard is a non-atomic check with no DB constraint or lock"), which reports the identical check-then-insert defect on the same lines from the perspective of the manual-vs-pipeline race. Same root defect as **XCT-02**.

**Locations:** `backend/app/services/apply.py:49` (`ApplyService.enqueue_apply`); also `backend/app/services/apply.py:72` (`enqueue_auto_apply_from_pipeline`), `backend/app/repositories/application_logs.py:38` (`get_pending_for_job`), `backend/app/models/application_log.py:16`.

**Evidence.** Both enqueue paths call `get_pending_for_job(job.id)` — a plain `SELECT` with no `with_for_update` (`application_logs.py:38`) — and then `application_logs.add(...)`. There is no `UniqueConstraint` on `application_log` for pending non-dry-run rows, unlike `pending_digest` which carries `uq_pending_digest_seen_job` from migration 0005. Two concurrent callers therefore both observe `None` and both insert a `queued` row.

**Failure scenario.** Two concurrent `POST /jobs/{id}/apply` (or a manual apply racing the pipeline auto-apply, or a double-click) both pass the guard, queue two live applies, and submit the same real application twice to the ATS/employer.

**Suggested fix.** Add a partial unique index on `seen_job_id` scoped to pending, non-dry-run rows, or `SELECT ... FOR UPDATE` the job/existing-log row before the check-and-insert so the guard is atomic.

**Verification.** Confirmed 3/3 adversarial verifiers (SVC-01) and 3/3 on the merged SVC-03. `get_pending_for_job` is a plain SELECT with no lock and `application_log` has no unique constraint (unlike `pending_digest`'s uq in migration 0005), so two concurrent enqueues both see `None` and insert queued rows, yielding a duplicate live ATS submit.

**Resolution.** Closed with **XCT-02**: `uq_application_log_inflight_job` + `try_add_pending` (shipped in `334164a`; tracker/docs in XCT-02 drain PR).

<a id="svc-02"></a>
### SVC-02 — Auto-apply has no per-plan or volume cap once a source opts in
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/12)) · Confidence: high (3/3 verifiers) · Effort: M · WS14

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/12): `PlanLimits.max_auto_applies_per_day` (Free 3 / Starter 5 / Plus 10 / Pro 20) is enforced in `_pipeline_auto_apply_eligible` via `PlanLimitsService.allows_pipeline_auto_apply`, counting live (non–dry-run) `application_log` rows in a rolling 24h window. Cap exceeded → silent skip (matches other pipeline eligibility skips). Manual Jobs-page Apply is unchanged. Merged SVC-08 closed by the same guard.

> Merged with **SVC-08** ("Auto-apply has no per-run/daily/plan volume cap"), which reports the same missing guardrail from the `queue_auto_applies_for_new_jobs` fan-out side.

**Locations:** `backend/app/services/apply.py:62` (`ApplyService.enqueue_auto_apply_from_pipeline` / `_pipeline_auto_apply_eligible`); also `backend/app/services/pipeline_auto_apply.py:17` (`queue_auto_applies_for_new_jobs`), `backend/app/services/apply.py:255`, `backend/app/services/plan_limits.py`, `backend/app/core/plans.py:48-49`.

**Evidence.** `_pipeline_auto_apply_eligible` gates only on `source.auto_apply_enabled` + `has_applier` + `profile.exists` (apply.py:255-265). `PlanFeatures` in `plans.py` has no auto-apply gate and `PlanLimitsService` has no apply cap; `queue_auto_applies_for_new_jobs` loops over ALL new postings unbounded. `launch-checklist.md:111` explicitly states auto-apply is NOT "unattended bulk applying".

**Failure scenario.** A source with `auto_apply_enabled=True` scrapes N new postings in one run; the worker fires N live applications with the user's credentials in a single tick, with no daily, per-run, per-total, or per-plan ceiling.

**Suggested fix.** Add a per-user/per-plan auto-apply volume cap (per run and/or rolling window), enforced in `enqueue_auto_apply_from_pipeline` before queueing, e.g. by counting live `application_log` rows in a window.

**Verification.** Confirmed 3/3 adversarial verifiers (SVC-02) and 3/3 on the merged SVC-08. Eligibility checks only `auto_apply_enabled`/`applier`/`profile` with no per-plan or volume cap anywhere in `plans.py` or `plan_limits.py`, and the queue loops all postings; the launch checklist itself says auto-apply is not unattended bulk applying.

<a id="svc-04"></a>
### SVC-04 — Digest flush tick has no per-search exception isolation
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/13)) · Confidence: high (5/5 verifiers) · Effort: S · WS14

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/13): `flush_due` wraps each `_flush_search` in `try/except` (log + continue) and `session.commit()`s after each successful flush. Merged SVC-05 closed by the same per-search commit.

**Locations:** `backend/app/services/digest.py:64` (`DigestService.flush_due`); also `backend/app/worker/tasks.py:137`, `backend/app/notifiers/adapters/webhook.py:46`.

**Evidence.** `flush_due` loops over all searches calling `_flush_search` with no `try/except`; `_flush_search` re-raises on a `notifier.send` failure. `webhook.send` raises `ValueError` on a missing `config.webhook_url` or an SSRF-blocked URL, and `TargetCreate.config` is unvalidated. The whole beat task shares one `session_scope`.

**Failure scenario.** A digest target with an empty or blocked webhook config makes `_flush_search` raise on every `flush_due_digests` tick, rolling back the tick: other users' due digests never send, and digests already sent over the wire that tick re-send next tick.

**Suggested fix.** Wrap each `_flush_search` in `try/except` inside `flush_due` (log/record the error, continue) and commit per-search, so one bad target cannot block or roll back other searches' digests.

**Verification.** Confirmed 5/5 adversarial verifiers. `flush_due` lacks per-search `try/except`; `_flush_search` re-raises and only flushes (single `session_scope` commits at end), so one webhook target with an empty/blocked URL (config unvalidated) rolls back the whole tick, blocking other users' digests and re-sending already-POSTed ones.

<a id="svc-05"></a>
### SVC-05 — Digest flush sends before commit; a later search failure re-sends earlier digests
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/13)) · Confidence: high (3/3 verifiers) · Effort: S · WS14

**Update (2026-07-10).** Fixed together with SVC-04 in [PR](https://github.com/davidcristian/HeadStart/pull/13): each successful `_flush_search` commits before the next search, so a later notifier failure cannot roll back already-delivered digest bookkeeping.

**Locations:** `backend/app/services/digest.py:57` (`DigestService.flush_due` / `_flush_search`); also `backend/app/worker/tasks.py:139`, `backend/app/services/digest.py:112`.

**Evidence.** `flush_due` loops all pending searches in ONE transaction; `_flush_search` calls `notifier.send` (irreversible SMTP/webhook) and then only `self.session.flush()` for `last_digest_at` + `delete_for_search`. `session_scope` commits once at the end and rolls back on any error (`core/db.py:34-36`), so the delivered side effect and its bookkeeping are not atomic.

**Failure scenario.** Search A's digest is sent, then search B's `notifier.send` raises → the whole transaction rolls back, losing A's `last_digest_at` update and pending-delete; the next beat tick re-sends A's digest, producing duplicate notifications.

**Suggested fix.** Commit (or use a savepoint) per-search after each successful `_flush_search`, so a later search's failure cannot roll back an already-delivered digest's bookkeeping.

**Verification.** Confirmed 3/3 adversarial verifiers. `flush_due` runs all searches in one `session_scope` (rollback-on-error); `_flush_search` sends irreversibly then only flushes `last_digest_at`/delete, so a later search's send raise rolls back an earlier delivered digest's bookkeeping and the next tick re-sends (no idempotency check).

<a id="svc-06"></a>
### SVC-06 — Ghost-detection loop lacks per-item exception isolation vs orchestration
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/14)) · Confidence: medium (3/3 verifiers) · Effort: S · WS14

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/14): `process_due` wraps each `_process_job` in `try/except` (log + `failed+=1` + continue) and commits after each successful ghost so a later raise cannot roll back earlier `ghosted_at` via `session_scope`.

**Locations:** `backend/app/services/ghost_detection.py:51` (`GhostDetectionService.process_due`); also `backend/app/services/ghost_detection.py:89`.

**Evidence.** The loop `for user_id, job in ...: outcome = self._process_job(...)` has no `try/except`. `_process_job` calls `self.inbox.send_message`, which can raise (`resolve_context` `ValidationError`, token-refresh `httpx` errors). The sibling `InboxOrchestrationService._process_user` wraps its fetch in `try/except` and returns `failed=1`, showing the intended pattern is per-item isolation.

**Failure scenario.** One user's token-refresh or send raises mid-loop; the whole `detect_ghosted_applications` task aborts, `session_scope` rolls back the already-set `ghosted_at` flushes for earlier users, and remaining users are never checked.

**Suggested fix.** Wrap `_process_job` per iteration in `try/except`, log and count it as failed, and continue — mirroring `inbox_orchestration`'s per-user isolation.

**Verification.** Confirmed 3/3 adversarial verifiers. `process_due` loops `_process_job` with no `try/except`; `resolve_context` can raise `ValidationError`/token-refresh errors and `send_message` can raise network errors, so one user's failure aborts the task and rolls back earlier `ghosted_at` flushes; the sibling `inbox_orchestration` wraps per-user.

<a id="svc-07"></a>
### SVC-07 — Premium scraper/notifier gates not re-checked at pipeline run (survive downgrade)
🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: M · WS14

**Locations:** `backend/app/services/pipeline.py:105` (`PipelineService.run`); also `backend/app/services/pipeline.py:155`, `backend/app/services/pipeline.py:257`, `backend/app/services/billing.py:226`, `backend/app/services/admin.py:41`.

**Evidence.** `run()`/`scrape()`/`_notify()` resolve the scraper/notifier by `adapter_key` with no `scraper_allowed`/`notifier_allowed` check; only `allows_summaries()` (L105) is gated. The `require_can_add_source`/`require_can_add_target` checks run ONLY on create/update (`sources.py:46`, `targets.py:33`), never at consumption time.

**Failure scenario.** A Plus user configures a linkedin/playwright source or a webhook target, then their subscription is canceled (`billing.py:226` sets `plan=free`) or an admin downgrades them. The paid source/notifier keeps scraping and delivering on every scheduler tick because the gate is never re-evaluated.

**Suggested fix.** Re-check `scraper_allowed`/`notifier_allowed` (and over-cap searches) at pipeline run time, or reconcile/disable over-plan resources on downgrade in `_on_subscription_deleted` and `admin.update_user`.

**Verification.** Confirmed 5/5 adversarial verifiers. `require_can_add_source`/`target` run only at create; `pipeline.run` re-checks only `allows_summaries`; `_on_subscription_deleted`/updated set the plan without reconciling over-plan resources. Rated medium (not higher) because the leakage is bounded revenue/feature access — not PII or cross-tenant — and requires a prior paid subscription then a downgrade.

<a id="svc-09"></a>
### SVC-09 — Alerts broadcast to ALL user targets when search has no target
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (2/3 verifiers) · Effort: S · WS35

**Locations:** `backend/app/services/application_alerts.py:117` (`_resolve_targets`).

**Evidence.** `_resolve_targets` falls back to `self.targets.list_all(user_id)` whenever `job.search.target_id` is `None`, so `_send_alert` loops over every target and sends the same posting to each — one recovery event can page every configured channel.

**Failure scenario.** A user with multiple notification targets whose search has no `target_id` receives the same ghost-recovery / interview-handoff alert delivered to every target simultaneously (duplicate fan-out).

**Suggested fix.** Resolve a single default/preferred target for alerts instead of broadcasting to all, or document the broadcast as intended behavior.

**Verification.** Confirmed 2/3 adversarial verifiers. `Search.target_id` is nullable; `_resolve_targets` falls back to `targets.list_all(user_id)`, so ghost/interview alerts for a no-target search fan out one event to every channel — real duplicate delivery, low and recoverable.

<a id="svc-10"></a>
### SVC-10 — derive_pipeline_stage final branch is dead code
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: certain (3/3 verifiers) · Effort: XS · WS35

**Locations:** `backend/app/services/applications.py:51` (`derive_pipeline_stage`).

**Evidence.** The branch `if job.status == 'applied' or (latest ... 'submitted'): return 'awaiting_reply'` is immediately followed by an unconditional `return 'awaiting_reply'`. The condition never changes the outcome, so the branch is a no-op that obscures the state-machine intent.

```python
if job.status == "applied" or (latest and latest.status == "submitted"):
    return "awaiting_reply"
return "awaiting_reply"
```

**Failure scenario.** No runtime impact; the redundant branch hides that `applied`/`submitted` and the default collapse to the same stage, making the state machine harder to maintain.

**Suggested fix.** Collapse to a single `return 'awaiting_reply'`, or give `applied`/`submitted` a distinct stage if one was intended.

**Verification.** Confirmed 3/3 adversarial verifiers. Lines 51-53 confirm the guarded branch returns `'awaiting_reply'` immediately before an unconditional `return 'awaiting_reply'` — genuinely dead/redundant code with no behavioral effect.

<a id="svc-11"></a>
### SVC-11 — Adapter payload merged verbatim into stored application_log (no scrub)
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (2/3 verifiers) · Effort: S · WS35

**Locations:** `backend/app/services/apply.py:238` (`_merge_tracking_payload`); also `backend/app/services/apply.py:215`, `backend/app/services/apply.py:233`, `backend/app/appliers/types.py:20`.

**Evidence.** `_merge_tracking_payload` does `{**tracking, **adapter_payload}` and stores the result on `ApplicationLog.payload` (JSON, plaintext). `ApplyContext.credentials` (decrypted cookies/headers) are handed to the adapter, and nothing stops an adapter echoing them into `result.payload`, which is then persisted unencrypted and exposed via the read path.

**Failure scenario.** An applier adapter that includes request headers/cookies in `result.payload` persists decrypted session credentials in plaintext in `application_log` and exposes them via `/application-logs` responses.

**Suggested fix.** Whitelist/scrub adapter payload keys (drop cookies/headers/authorization) before persisting in `_merge_tracking_payload`.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). `_merge_tracking_payload` does `{**tracking, **adapter_payload}` onto the plaintext `ApplicationLog.payload` with no scrub; no current adapter echoes credentials, so the impact is unrealized, but it is a legitimate defense-in-depth low as the finding itself scopes it.

<a id="svc-12"></a>
### SVC-12 — _annualize treats monthly/weekly/daily comp intervals as already-annual
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS35

**Locations:** `backend/app/services/compensation.py:208` (`_annualize`).

**Evidence.** Only `_ANNUAL_INTERVALS` and `_HOURLY_INTERVALS` are handled; any other interval (e.g. Ashby `'MONTH'`/`'WEEK'`/`'DAY'`) falls through to `return value`, storing the raw per-period figure as if it were annual.

**Failure scenario.** An Ashby posting with interval `'MONTH'` and `minValue` 8000 is recorded as $8,000/yr; a `min_salary` filter of 80k wrongly filters it out, and the stored/displayed salary is wrong by roughly 12x.

**Suggested fix.** Add `MONTH`/`WEEK`/`DAY` interval sets with multipliers (12 / 52 / 260) in `_annualize`; leave unknown intervals as pass-through.

**Verification.** Confirmed 3/3 adversarial verifiers. `_annualize` handles only annual/hourly; `ashby_parse` sets `raw=job` so the compensation interval (Ashby uses MONTH/WEEK/DAY) falls through to pass-through, storing a ~12x-wrong salary that mis-filters via `meets_min_salary` — a real narrow correctness bug.

<a id="svc-13"></a>
### SVC-13 — Compensation parser assumes US number grouping, misreads EU-formatted salaries
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS35

**Locations:** `backend/app/services/compensation.py:186` (`_parse_amount`); also `backend/app/services/compensation.py:14`.

**Evidence.** `_AMOUNT_RE` treats `','` as a grouping char and `'.'` as decimal, and `_parse_amount` does `digits.replace(",", "")`. For a German posting `'55.000 €'` (dot = thousands) this parses `55.000` → `int(55)`, and `'1.234,56'` would be mis-split — the EU decimal comma is not handled.

**Failure scenario.** A EUR posting listing `'€55.000'` is parsed as €55 (or €0/€1), so min-salary filters and displayed compensation are wildly wrong for European postings.

**Suggested fix.** Detect locale/currency and handle EU grouping (dot thousands, comma decimal) before coercing amounts.

**Verification.** Confirmed 3/3 adversarial verifiers. `_AMOUNT_RE` treats `'.'` as decimal and strips `','`; `'55.000'` parses via `float('55.000')` → 55; sites like indeed/workday/lever/greenhouse serve EU postings and no upstream locale guard exists, so EUR comma/dot formats are misread.

<a id="svc-14"></a>
### SVC-14 — Compensation display currency prefix silently falls back to '$' for unknown currencies
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: XS · WS35

**Locations:** `backend/app/services/compensation.py:242` (`_format_currency_prefix`).

**Evidence.** `_format_currency_prefix` returns `'$'` as the default for any currency that is not exactly `'EUR'`/`'GBP'` (e.g. `'CHF'`, `'SEK'`, or `None`). Only three currencies are mapped in `_CURRENCY_SYMBOLS`/`_CODE_RE`, so a CHF or SEK posting is rendered with a US dollar sign.

**Failure scenario.** A Swiss/Nordic posting with a recognized amount but an unmapped currency displays a `'$'` prefix, mislabeling the salary currency for European users.

**Suggested fix.** Use the ISO code as prefix/suffix when no symbol is known instead of defaulting to `'$'`, or expand the symbol map.

**Verification.** Confirmed 3/3 adversarial verifiers. `_format_currency_prefix` returns `'$'` for anything not EUR/GBP (CHF/SEK/NOK/None), and `_CURRENCY_SYMBOLS`/`_CODE_RE` only cover USD/EUR/GBP, so unmapped currencies are mislabeled with a dollar sign; no guard restricts currency to those three.

<a id="svc-15"></a>
### SVC-15 — DigestService.queue inserts and flushes once per seen_job id in a loop
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: XS · WS33

**Locations:** `backend/app/services/digest.py:40` (`queue`); also `backend/app/repositories/digest.py:16`.

**Evidence.** `queue()` loops over `seen_job_ids` calling `self.pending.add()`, and `add()` does `session.add` + `session.flush()` per row. Persisting a batch of newly-notified digest jobs therefore triggers one flush (DB round-trip) per job rather than one batched flush.

**Failure scenario.** A search that discovers many new postings in one run flushes the DB once per posting when queueing the digest, multiplying write round-trips in the hot pipeline path.

**Suggested fix.** Add all `PendingDigest` rows then flush once (`add_all` / single flush), or expose a batch add on the repository.

**Verification.** Confirmed 3/3 adversarial verifiers. `repositories/digest.py` `add()` does `session.add`+`session.flush` per row and `DigestService.queue` loops calling it, so a batch of newly-seen jobs triggers one flush round-trip per job in the hot pipeline path.

<a id="svc-16"></a>
### SVC-16 — RSS builder escapes markup but leaves XML-invalid control chars from scraped fields
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: XS · WS35

**Locations:** `backend/app/services/rss.py:37` (`_render_item`); also `backend/app/services/rss.py:28`.

**Evidence.** `title`/`company`/`location`/`summary` come from the scraped `JobPosting` (`pipeline.py:216-223`, untrusted per AGENTS.md §7) and pass only through `xml.sax.saxutils.escape`, which handles `&<>` but not C0 control chars (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F) forbidden by XML 1.0 §2.2.

**Failure scenario.** A scraped title containing e.g. 0x0C or 0x1B yields well-formed-invalid XML; strict RSS readers reject the entire feed document, breaking that user's feed for all jobs.

**Suggested fix.** Strip/replace XML-invalid control characters (keeping tab/LF/CR) before escaping each text field in `build_rss_feed`/`_render_item`.

**Verification.** Confirmed 3/3 adversarial verifiers. `escape` only handles `&<>`; scraped title/summary reach `_render_item` with no upstream C0-control-char stripping (grep found no sanitizer), so a control char yields well-formed-invalid XML that strict readers reject.
