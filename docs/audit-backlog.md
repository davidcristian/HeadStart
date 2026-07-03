# Audit Backlog

Living tracker for issues found in the codebase audit (2026-07-01). Same spirit as
[roadmap.md](roadmap.md), but for **bugs, tech-debt, and doc drift** rather than new
features. Update the Status column (and strike the row) when an item ships; link the PR.

Produced by a read-only multi-agent audit — 13 subsystem clusters, every finding
adversarially verified against the code. **77 confirmed** findings (1 critical, 9 high,
16 medium, 51 low). 6 of them (the whole browser-extension cluster) are already resolved
by removing the extension.

**Status legend:** ☐ open · 🔜 in progress · ✅ done
**Type:** 🐞 bug · 🔒 security · 📝 doc · 🧪 test · ♻️ refactor · 🔁 consistency

---

## At a glance — highest priority (open)

| Sev | Item | Where |
| --- | ---- | ----- |
| 🔴 CRIT | Outlook/Fastmail message UIDs (~1.8e21) overflow even `BigInteger`; columns are 32-bit `Integer` — breaks inbox on Postgres | `inbox/outlook_ids.py`, `inbox/fastmail_ids.py` |
| 🟠 HIGH | Gmail hex→int UID overflows 32-bit `Integer` poll/classification columns | `inbox/gmail_ids.py:9` |
| 🟠 HIGH | Scheduler enqueues due searches with no lease → overlapping ticks double-notify | `worker/tasks.py:67` |
| 🟠 HIGH | Default `jwt_secret`/`credentials_secret_key` not rejected in prod (forgeable tokens) | `core/config.py:38` |
| 🟠 HIGH | `.localhost` (and reserved TLDs) skip all SSRF DNS/IP checks | `core/outbound_url.py:42` |
| 🟠 HIGH | Meta apply: work-history parallel arrays desync → wrong employer/title/date pairing | `appliers/adapters/meta_careers_payload.py:58` |

---

## WS1 — Inbox message-UID integer overflow
Dev-only feature (`inbox_agent_enabled=False`), but broken on Postgres the moment a real
message arrives (SQLite's arbitrary-precision ints hide it in tests).

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🔴 CRIT | 🐞 | Outlook/Fastmail `micros * (1<<20)` ≈ 1.8e21 (~71-bit) exceeds `BigInteger`; narrow the encoding (seconds + smaller tail → <2⁶³) **and** widen columns | `inbox/outlook_ids.py:17` | ☐ |
| 🟠 HIGH | 🐞 | Gmail `int(gmail_id,16)` ≈ 61-bit overflows 32-bit `Integer`; widen `last_polled_uid`/`message_uid` cols to `BigInteger` (+ migration) | `inbox/gmail_ids.py:9` | ☐ |
| 🟡 MED | 🐞 | Gmail hex ids aren't chronologically ordered → #168 oldest-first sort unreliable, can permanently skip mail; add a time component | `inbox/adapters/gmail.py:202` | ☐ |
| ⚪ LOW | 🔁 | OAuth refresh persists config via `model_dump_json()` while readers expect `encode_mailbox_config` | `services/inbox_oauth.py:59` | ☐ |
| ⚪ LOW | 🧪 | Yahoo/IMAP oldest-first (#168) has no test guarding the drop-old-mail regression | `inbox/adapters/yahoo.py:62` | ☐ |
| ⚪ LOW | 📝 | `inbox.md` says Gmail ids map to "integer uid values" without noting the overflow | `docs/modules/inbox.md:56` | ☐ |

## WS2 — Scheduler double-enqueue → duplicate notifications
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | `enqueue_due_searches` has no claim/lease; a scrape >`SCHEDULER_TICK_SECONDS` gets re-enqueued → duplicate notify + double `pending_digest`/auto-apply. Fix: atomic `UPDATE … RETURNING id` claim | `worker/tasks.py:67` | ☐ |
| ⚪ LOW | 🐞 | `flush_due_digests` has no concurrency guard → overlapping ticks can double-send a digest | `services/digest.py:48` | ☐ |
| ⚪ LOW | 🔁 | Ghost-recovery / interview-handoff alerts skip the `DeliveryLog` audit row every other path writes | `services/email_classification.py:142` | ☐ |
| ⚪ LOW | 🧪 | No test for `enqueue_due_searches` / beat double-enqueue | `worker/tasks.py:58` | ☐ |

## WS3 — Security hardening
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🔒 | No validator rejects placeholder `jwt_secret`/`credentials_secret_key` when `environment` is non-local (forgeable JWTs, decryptable secrets). Add `@model_validator` that fails fast | `core/config.py:38` | ☐ |
| 🟠 HIGH | 🔒 | `host.endswith(_TEST_TLD_SUFFIXES)` early-returns for `.localhost` (resolves to loopback) → SSRF bypass on user source URLs. Drop `.localhost` / gate behind a test flag | `core/outbound_url.py:42` | ☐ |
| ⚪ LOW | 🔒 | `/metrics` bearer token compared with `!=` (not constant-time) → use `hmac.compare_digest` | `main.py:50` | ☐ |

## WS4 — Apply-adapter correctness
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | Meta `build_application_state` filters name/title/location per-column but iterates all rows for dates → arrays desync, wrong pairing. Build every `work*` column from one filtered list | `appliers/adapters/meta_careers_payload.py:58` | ☐ |
| 🟡 MED | 🐞 | Microsoft `build_answers` returns whole `profile.answers` verbatim (questionnaire mapping is dead code); drive from fetched questions | `appliers/adapters/microsoft_careers_payload.py:63` | ☐ |
| 🟡 MED | 🐞 | Ashby `allow_unpublished_job_posting:false` guard dropped on multipart (resume) submits | `appliers/adapters/ashby.py:241` | ☐ |
| 🟡 MED | 🧪 | No regression test for Meta multi-row array alignment | `tests/appliers/test_meta_careers.py:142` | ☐ |
| ⚪ LOW | 🐞 | Uber treats every additional question as required → blocks live apply on optional questions | `appliers/adapters/uber_careers_questions.py:80` | ☐ |
| ⚪ LOW | 🔁 | Greenhouse live submit lacks the post-2xx error-body check its siblings have | `appliers/adapters/greenhouse.py:95` | ☐ |
| ⚪ LOW | 🧪 | No test for Ashby multipart dropping the guard | `tests/appliers/test_ashby.py:90` | ☐ |
| ⚪ LOW | ♻️ | `render_cover_letter`/`split_name` copy-pasted across 5/3 appliers; extract a shared helper | `appliers/adapters/workday_payload.py:20`, `ashby.py:135` | ☐ |
| ⚪ LOW | ♻️ | Workday re-implements `structured_profile.applicable_*` verbatim (Uber imports them) | `appliers/adapters/workday_experience.py:45` | ☐ |
| ⚪ LOW | ♻️ | SmartRecruiters `consent` fallback branch is dead code | `appliers/adapters/smartrecruiters_payload.py:110` | ☐ |

## WS5 — Billing correctness
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | `plan_upgrade` promo never upgrades — line item keeps requested plan's price; recompute `price_id` from `promo.plan_target` | `services/billing.py:105` | ☐ |
| 🟡 MED | 🐞 | Unknown/absent subscription price silently returns `"pro"` (grants top tier free); default to `free`/`starter` + warn | `services/billing.py:228` | ☐ |
| 🟡 MED | 🐞 | Promo redemption read-then-write with no unique constraint → webhook retry/concurrency double-counts. Add `UniqueConstraint(promo_code_id,user_id)` + `IntegrityError` no-op | `services/promo_codes.py:117` | ☐ |
| 🟡 MED | 🐞 | `free_trial_days` promos get no Stripe cap and no effective global cap (counter only bumps at webhook). Reserve at checkout | `services/promo_codes.py:73` | ☐ |
| ⚪ LOW | 🧪 | No test for webhook idempotency / duplicate redemption / global cap | `tests/api/test_promo_codes.py:114` | ☐ |
| ⚪ LOW | 📝 | Billing doc omits promo model/repo/schema; overstates refund policy | `docs/modules/billing.md:3` | ☐ |

## WS6 — Scraper input-hardening
Untrusted upstream JSON/HTML aborts the whole scrape where siblings degrade to `None`/`[]`.
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | Unguarded `datetime.fromisoformat` in ashby/smartrecruiters (also snowflake via ashby) → one bad date aborts the run | `scrapers/adapters/ashby_parse.py:53`, `smartrecruiters.py:130` | ☐ |
| 🟡 MED | 🐞 | Unguarded `json.loads` on HTML-extracted blob crashes google_careers parse | `scrapers/adapters/google_careers_parse.py:55` | ☐ |
| ⚪ LOW | 🐞 | Untrusted flight-stream ref key → `int(ref_key[1:])` crashes shopify `_resolve_node` | `scrapers/adapters/shopify_careers_parse.py:80` | ☐ |
| ⚪ LOW | 🐞 | `int()` of untrusted total/count overflows on JSON `Infinity/NaN` | `scrapers/adapters/smartrecruiters.py:53` | ☐ |
| ⚪ LOW | 🔁 | `post_json`/`post_form` skip the upfront `assert_safe_outbound_url` sibling methods do (hook still covers it) | `scrapers/http.py:51` | ☐ |
| ⚪ LOW | 🧪 | No test for the test-TLD SSRF bypass or redirect re-validation | `tests/core/test_outbound_url.py:8` | ☐ |

## WS7 — Frontend correctness
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | `/app/settings` renders outside `<Layout>` → user stranded with no nav | `frontend/src/App.tsx:61` | ☐ |
| 🟡 MED | 🐞 | `useDraftInboxReply` invalidates over-specific `["applications",null]` → stage-filtered pipeline never refreshes | `frontend/src/hooks/mutations.ts:251` | ☐ |
| 🟡 MED | 🐞 | Portals effect resets `selectedIds` to all on every catalog refetch → undoes manual deselection | `frontend/src/pages/portals/usePortalsPage.ts:32` | ☐ |
| ⚪ LOW | 🐞 | `useSubscribePortals` invalidates over-specific portals key → filtered caches stale | `frontend/src/hooks/mutations.ts:236` | ☐ |
| ⚪ LOW | 🐞 | Applying from Jobs page never invalidates the `applications` pipeline cache | `frontend/src/hooks/jobMutations.ts:39` | ☐ |
| ⚪ LOW | 🔁 | `FreeTierAd` reads consent from `localStorage`, not `CookieConsentContext` (non-reactive) | `frontend/src/components/FreeTierAd.tsx:20` | ☐ |
| ⚪ LOW | 🧪 | Auth guards (EmailVerification/Onboarding/AdminRoute) have no tests | `frontend/src/App.test.tsx:40` | ☐ |
| ⚪ LOW | 🧪 | `AuthContext.test` fixture omits the now-required `email_verified_at` | `frontend/src/auth/AuthContext.test.tsx:7` | ☐ |
| ⚪ LOW | 📝 | Docs say register → `/app/onboarding`; code goes `/verify-email` | `frontend/src/pages/RegisterPage.tsx:32` | ☐ |

## WS8 — Remove the browser extension ✅ DONE (2026-07-01)
We are no longer shipping a browser extension. Deleted `browser-extension/` and
`docs/modules/browser-extension.md`; purged references from README, docs, roadmap,
pricing/landing copy, and setup/test scripts; kept `POST /sources/detect` (used by
onboarding). This resolved 6 findings that were open against the extension (4 high, 2 low).

## WS9 — Reply-drafter prompt-injection sanitization
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | Reply drafter feeds **raw** recruiter body into the LLM (this path can auto-send over SMTP). Sanitize via existing `email_classifiers/sanitize.py` | `services/reply_drafts.py:185` | ☐ |
| ⚪ LOW | 📝 | Docs imply only the classifier guards injection; reply-drafter gap undocumented | `docs/modules/inbox.md:216` | ☐ |
| ⚪ LOW | 🧪 | No test for reply-draft injection handling | `tests/email_classifiers/test_sanitize.py:1` | ☐ |

## WS10 — LLM-adapter-family consolidation (refactor, ~1,800 LOC)
Five families (`summarizers`/`resumes`/`cover_letters`/`email_classifiers`/`reply_drafters`)
reimplement near-identical provider adapters + registries. **Approved direction:** one
dedicated consolidation PR. The Gemini security fix should ship regardless.
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | Gemini API key in URL query string in 4 of 5 families (loggable); use `x-goog-api-key` header like `email_classifiers` | `*/adapters/gemini.py` | ☐ |
| ⚪ LOW | 🔁 | Gemini adapters diverge (key-in-URL vs header; model quoting) | `email_classifiers/adapters/gemini.py:36` | ☐ |
| ⚪ LOW | ♻️ | `summarizers/` duplicate all response/auth helpers instead of using shared `llm_common` (already drifted) | `summarizers/adapters/openai.py:113` | ☐ |
| ⚪ LOW | ♻️ | Shared helpers oddly live under `cover_letters/adapters/llm_common.py`, re-exported by peers (layering smell) | `cover_letters/adapters/llm_common.py:1` | ☐ |
| ⚪ LOW | ♻️ | Per-family `base.py` registry is 5× copy-paste | `reply_drafters/base.py:19` | ☐ |
| ⚪ LOW | ♻️ | Dead `logger` binding in all 4 summarizer adapters | `summarizers/adapters/openai.py:23` | ☐ |
| ⚪ LOW | 🔁 | `heuristic.__init__` signature differs in `summarizers` only | `summarizers/adapters/heuristic.py:27` | ☐ |

## WS11 — Documentation updates
(Doc rows also live under their subsystem above; these are the docs-cluster + infra items.)
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 📝 | `SCHEDULER_MAX_CATCHUP` is a dead setting — in config/.env/docs but never read. Delete it (preferred) or implement; fix worker.md + architecture.md | `docs/modules/worker.md:32` | ☐ |
| ⚪ LOW | 📝 | 6 `config.py` Settings fields undocumented in `.env.example` | `.env.example:134` | ☐ |
| ⚪ LOW | 📝 | `SUMMARY_PROVIDER` comment omits shipped `anthropic` provider | `.env.example:93` | ☐ |
| ⚪ LOW | 📝 | `inbox.md` API table omits Outlook OAuth routes + `/reply-send-log` | `docs/modules/inbox.md:179` | ☐ |
| ⚪ LOW | 📝 | `scrapers.md` rate-limit table lists 13 of 17 adapters | `docs/modules/scrapers.md:95` | ☐ |
| ⚪ LOW | 📝 | `api.md` calls `/billing/checkout` Pro-only (accepts starter\|plus\|pro) | `docs/modules/api.md:84` | ☐ |
| ⚪ LOW | 📝 | `appliers.md`: undocumented Ashby `allow_unpublished_job_posting`; stale SmartRecruiters `consent`; Lever `compliance_policy_id`/`gdpr_consent` coupling | `docs/modules/appliers.md`, `appliers/adapters/lever.py:240` | ☐ |
| ⚪ LOW | 📝 | `catalog.py` docstring says edit `catalog_presets.py`, but ~40 employers now live in `presets/<id>.py` | `portals/catalog.py:4` | ☐ |

## WS12 — Test-coverage backfill
(Item-specific tests are tracked in each WS above; these are the standalone gaps.)
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| ⚪ LOW | 🧪 | Multi-user isolation invariant has almost no cross-user tests (only `sources`); add for searches/targets/credentials/jobs/applications | `tests/api/test_api.py:178` | ☐ |
| ⚪ LOW | 🧪 | `core/security.py` has no direct tests (JWT type enforcement, bcrypt 72-byte truncation, feed-token version) | `core/security.py:106` | ☐ |
| ⚪ LOW | 🔁 | `apple_careers` omitted from the single-employer set in `_config_keys_match` (diverges from 7 siblings) | `services/portals.py:92` | ☐ |
| ⚪ LOW | 🧪 | No test for the single-employer dedup branch in `_config_keys_match` | `tests/services/test_portals.py:105` | ☐ |
| ⚪ LOW | 🔁 | Inbox router duplicates the `require_enabled()` gate its service already applies | `api/v1/inbox.py:290` | ☐ |
| ⚪ LOW | ♻️ | Dead schemas `ApplicationLogListParams`, `ApplicationPipelineListParams` | `schemas/application_pipeline.py:62` | ☐ |

---

## Suggested PR sequencing (safest first)
1. **WS3** (security) + **WS11** (docs) — small, high value, low risk.
2. **WS1** (inbox UID overflow) + **WS2** (scheduler dup-notify) — correctness-critical.
3. **WS5** (billing) + **WS6** (scrapers) + **WS4** (apply adapters).
4. **WS7** (frontend) + **WS9** (reply-drafter sanitization).
5. **WS10** (LLM refactor) + **WS12** (test backfill) — larger, do last.

Each PR: `make check` green before/after; every bug fix ships a regression test that fails
before and passes after; docs updated in the same PR (Definition of Done, AGENTS.md §5).
