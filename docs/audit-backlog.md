# Audit Backlog

Living tracker for issues found in the codebase audit (2026-07-01). Same spirit as
[roadmap.md](roadmap.md), but for **bugs, tech-debt, and doc drift** rather than new
features. Update the Status column (and strike the row) when an item ships; link the PR.

Produced by a read-only multi-agent audit — 13 subsystem clusters, every finding
adversarially verified against the code. **77 confirmed** findings (1 critical, 9 high,
16 medium, 51 low). 61 are already resolved: the browser-extension cluster (6) via
removal (WS8), the WS3 security-hardening trio (2 high + 1 low), the WS11 docs
cluster (8: 1 med + 7 low), all 6 WS1 inbox-UID items (1 crit + 1 high + 1 med
+ 3 low), all 4 WS2 scheduler items (1 high + 3 low), all 6 WS5 billing items
(4 med + 2 low), all 6 WS6 scraper-hardening items (2 med + 4 low), all 10
WS4 apply-adapter items (1 high + 3 med + 6 low), all 3 WS9 reply-drafter
sanitization items (1 med + 2 low), and all 9 WS7 frontend items (3 med + 6 low).

**Status legend:** ☐ open · 🔜 in progress · ✅ done
**Type:** 🐞 bug · 🔒 security · 📝 doc · 🧪 test · ♻️ refactor · 🔁 consistency

---

## At a glance — highest priority (open)

No open critical/high-severity items remain from the original audit — the last one (Meta
apply work-history array desync) is fixed in WS4. A later automated scan (Cursor, against
commit `5975194`) surfaced one **medium 🔒** item — password reset did not invalidate active
refresh sessions — now fixed in **WS13**. See the workstream tables below for the open
medium/low items.

---

## WS1 — Inbox message-UID integer overflow ✅ DONE (2026-07-01)
Dev-only feature (`inbox_agent_enabled=False`), but broken on Postgres the moment a real
message arrives (SQLite's arbitrary-precision ints hide it in tests). All six items fixed:
overflow (ms encoding + `BigInteger` columns), OAuth persistence, Gmail chronological
ordering (uid from `internalDate`; the list `after:` filter bounds the scan), and docs.

| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🔴 CRIT | 🐞 | Outlook/Fastmail `micros * (1<<20)` ≈ 1.8e21 (~71-bit) exceeded `BigInteger`; narrowed encoding to **milliseconds** (`millis<<20` ≈ 62-bit, safe to ~2255) **and** widened columns | `inbox/outlook_ids.py:17` | ✅ |
| 🟠 HIGH | 🐞 | Gmail `int(gmail_id,16)` ≈ 61-bit overflowed 32-bit `Integer`; widened `last_polled_uid`/`message_uid` cols to `BigInteger` (migration 0033) | `inbox/gmail_ids.py:9` | ✅ |
| 🟡 MED | 🐞 | Gmail hex ids aren't chronological → oldest-first sort could permanently skip mail; now derive the uid from `internalDate` and thread the raw id via headers for routing | `inbox/adapters/gmail.py:202` | ✅ |
| ⚪ LOW | 🔁 | OAuth refresh persisted config via `model_dump_json()` while readers expect `encode_mailbox_config`; unified on the shared encoder | `services/inbox_oauth.py:59` | ✅ |
| ⚪ LOW | 🧪 | Yahoo/IMAP oldest-first (#168) drop-old-mail regression — already guarded by the `*_over_limit` tests in `test_yahoo.py`/`test_imap_smtp.py` | `inbox/adapters/yahoo.py:62` | ✅ |
| ⚪ LOW | 📝 | `inbox.md` said Gmail ids map to "integer uid values" without noting the overflow; now documents `BigInteger` storage | `docs/modules/inbox.md:56` | ✅ |

## WS2 — Scheduler double-enqueue → duplicate notifications ✅ DONE (2026-07-01)
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | `enqueue_due_searches` had no claim/lease; a scrape >`SCHEDULER_TICK_SECONDS` got re-enqueued → duplicate notify + double `pending_digest`/auto-apply. Now `claim_due` advances `next_run_at` in-txn (`FOR UPDATE SKIP LOCKED` on Postgres) before enqueue | `worker/tasks.py:67` | ✅ |
| ⚪ LOW | 🐞 | `flush_due_digests` had no concurrency guard → overlapping ticks could double-send a digest; now each search is row-locked and re-checked under the lock | `services/digest.py:48` | ✅ |
| ⚪ LOW | 🔁 | Ghost-recovery / interview-handoff alerts skipped the `DeliveryLog` audit row every other path writes; `_send_alert` now records one per delivery | `services/application_alerts.py:62` | ✅ |
| ⚪ LOW | 🧪 | No test for `enqueue_due_searches` / beat double-enqueue; added `claim_due` regression + alert-DeliveryLog tests | `tests/worker/test_enqueue.py` | ✅ |

## WS3 — Security hardening ✅ DONE (2026-07-01)
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🔒 | No validator rejects placeholder `jwt_secret`/`credentials_secret_key` when `environment` is non-local (forgeable JWTs, decryptable secrets). Add `@model_validator` that fails fast | `core/config.py:38` | ✅ |
| 🟠 HIGH | 🔒 | `host.endswith(_TEST_TLD_SUFFIXES)` early-returns for `.localhost` (resolves to loopback) → SSRF bypass on user source URLs. Dropped `.localhost`; the remaining `.test/.example/.invalid` escape hatch is now gated to local/test so prod resolves + IP-checks them | `core/outbound_url.py:42` | ✅ |
| ⚪ LOW | 🔒 | `/metrics` bearer token compared with `!=` (not constant-time) → use `hmac.compare_digest` | `main.py:50` | ✅ |

## WS4 — Apply-adapter correctness
Shipping as two scoped PRs: **correctness bugs + tests (items 1–7) ✅ DONE (2026-07-01)**;
the three dedup refactors (items 8–10) follow in a separate PR.
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟠 HIGH | 🐞 | Meta `build_application_state` filtered name/title/location per-column but iterated all rows for dates → arrays desynced, wrong pairing. Now every `work*` column is built from one filtered list | `appliers/adapters/meta_careers_payload.py` | ✅ |
| 🟡 MED | 🐞 | Microsoft `build_answers` returned whole `profile.answers` verbatim (questionnaire mapping was dead code); now driven from the fetched questions so only asked-for answers are sent | `appliers/adapters/microsoft_careers_payload.py:63` | ✅ |
| 🟡 MED | 🐞 | Ashby `allow_unpublished_job_posting:false` guard was dropped on multipart (resume) submits; now carried into the multipart form too | `appliers/adapters/ashby.py:241` | ✅ |
| 🟡 MED | 🧪 | Added regression test for Meta multi-row array alignment | `tests/appliers/test_meta_careers.py` | ✅ |
| ⚪ LOW | 🐞 | Uber treated every additional question as required → blocked live apply on optional questions; now only API-`required` questions gate submit | `appliers/adapters/uber_careers_questions.py:80` | ✅ |
| ⚪ LOW | 🔁 | Greenhouse live submit lacked the post-2xx error-body check its siblings have; now fails on `success:false`/`error`/`errors` | `appliers/adapters/greenhouse.py:95` | ✅ |
| ⚪ LOW | 🧪 | Added test for Ashby multipart carrying the guard | `tests/appliers/test_ashby.py` | ✅ |
| ⚪ LOW | ♻️ | `render_cover_letter`/`split_name` copy-pasted across 5/3 appliers; extract a shared helper | `appliers/adapters/workday_payload.py:20`, `ashby.py:135` | ☐ |
| ⚪ LOW | ♻️ | Workday re-implements `structured_profile.applicable_*` verbatim (Uber imports them) | `appliers/adapters/workday_experience.py:45` | ☐ |
| ⚪ LOW | ♻️ | SmartRecruiters `consent` fallback branch is dead code | `appliers/adapters/smartrecruiters_payload.py:110` | ☐ |

## WS5 — Billing correctness ✅ DONE (2026-07-01)
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | `plan_upgrade` promo never upgraded — line item kept the requested plan's price; now the checkout price is recomputed from `promo.plan_target` (and metadata follows) | `services/billing.py:105` | ✅ |
| 🟡 MED | 🐞 | Unknown/absent subscription price silently returned `"pro"` (granted top tier free); now defaults to the lowest paid tier (`starter`) + logs a warning | `services/billing.py:228` | ✅ |
| 🟡 MED | 🐞 | Promo redemption read-then-write had no unique constraint → webhook retry/concurrency double-counted. Added `UniqueConstraint(promo_code_id,user_id)` (migration 0034) + `IntegrityError` no-op via savepoint | `services/promo_codes.py:117` | ✅ |
| 🟡 MED | 🐞 | `free_trial_days` promos had no Stripe cap and no effective global cap (counter only bumped at webhook); now reserved atomically at checkout (`reserve_global_slot` + per-user row) | `services/promo_codes.py:73` | ✅ |
| ⚪ LOW | 🧪 | Added tests for webhook idempotency, concurrent-duplicate redemption, and the global-cap reservation | `tests/services/test_promo_codes.py`, `tests/services/test_billing.py` | ✅ |
| ⚪ LOW | 📝 | Billing doc now documents the promo model/repo/schema, the cap/idempotency rules, and the (manual, non-automated) refund reality | `docs/modules/billing.md` | ✅ |

## WS6 — Scraper input-hardening ✅ DONE (2026-07-01)
Untrusted upstream JSON/HTML aborted the whole scrape where siblings degrade to `None`/`[]`;
now every parse degrades gracefully (see the Error handling note in `docs/modules/scrapers.md`).
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | Unguarded `datetime.fromisoformat` in ashby/smartrecruiters (also snowflake via ashby) → one bad date aborted the run; now via shared `scrapers/dates.py:parse_iso8601` (bad date → `None`) | `scrapers/adapters/ashby_parse.py`, `smartrecruiters.py` | ✅ |
| 🟡 MED | 🐞 | Unguarded `json.loads` on the HTML-extracted blob crashed google_careers parse; now returns `[]` on `JSONDecodeError` | `scrapers/adapters/google_careers_parse.py:55` | ✅ |
| ⚪ LOW | 🐞 | Untrusted flight-stream ref key → `int(ref_key[1:])` crashed shopify `_resolve_node`; now falls back to the literal key on `ValueError` and range-checks the index | `scrapers/adapters/shopify_careers_parse.py:80` | ✅ |
| ⚪ LOW | 🐞 | `int()` of an untrusted total overflowed on JSON `Infinity/NaN`; now `_coerce_count` returns a safe default for non-finite/negative/non-numeric | `scrapers/adapters/smartrecruiters.py:53` | ✅ |
| ⚪ LOW | 🔁 | `post_json`/`post_form` (and `put_json`/`post_multipart`) skipped the upfront `assert_safe_outbound_url` sibling methods do — matters for injected clients with no request hook; now all validate upfront | `scrapers/http.py:51` | ✅ |
| ⚪ LOW | 🧪 | Test-TLD SSRF bypass already covered (WS3, `test_outbound_url.py`); added redirect re-validation + upfront-method SSRF tests | `tests/scrapers/test_http_safety.py` | ✅ |

## WS7 — Frontend correctness ✅ DONE (2026-07-01)
Cache-invalidation fixes use the root prefix key (React Query matches by prefix) so every
stage/category-filtered cache refetches, not just the unfiltered one. `/app/settings` keeps its
pre-onboarding accessibility but now renders inside `<Layout>`. Portals selection is only reset
when the available catalog actually changes (keyed on the sorted id set), preserving manual
deselection across plain refetches.
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🐞 | `/app/settings` rendered outside `<Layout>` (no nav); now wrapped in its own `<Layout>`, still outside the verify/onboarding guards so it stays reachable pre-onboarding | `frontend/src/App.tsx:61` | ✅ |
| 🟡 MED | 🐞 | `useDraftInboxReply` invalidated over-specific `["applications",null]`; now invalidates the `["applications"]` prefix | `frontend/src/hooks/mutations.ts:251` | ✅ |
| 🟡 MED | 🐞 | Portals effect reset `selectedIds` to all on every catalog refetch; now keyed on the sorted catalog id set so only a real catalog change resets (hook test added) | `frontend/src/pages/portals/usePortalsPage.ts:32` | ✅ |
| ⚪ LOW | 🐞 | `useSubscribePortals` invalidated over-specific portals key; now invalidates the `["portals"]` prefix | `frontend/src/hooks/mutations.ts:236` | ✅ |
| ⚪ LOW | 🐞 | Applying from Jobs page never invalidated the pipeline; live (non-dry-run) apply now invalidates `["applications"]` | `frontend/src/hooks/jobMutations.ts:39` | ✅ |
| ⚪ LOW | 🔁 | `FreeTierAd` read consent from `localStorage`; now uses the reactive `useCookieConsent()` context (reactivity test added) | `frontend/src/components/FreeTierAd.tsx:20` | ✅ |
| ⚪ LOW | 🧪 | Added `src/auth/guards.test.tsx` covering EmailVerification/Onboarding/AdminRoute redirect + pass-through paths | `frontend/src/auth/guards.test.tsx` | ✅ |
| ⚪ LOW | 🧪 | `AuthContext.test` fixture now includes the required `email_verified_at` | `frontend/src/auth/AuthContext.test.tsx:7` | ✅ |
| ⚪ LOW | 📝 | Docs said register → `/app/onboarding`; corrected to `/verify-email` in `frontend.md` | `frontend/src/pages/RegisterPage.tsx:32` | ✅ |

## WS8 — Remove the browser extension ✅ DONE (2026-07-01)
We are no longer shipping a browser extension. Deleted `browser-extension/` and
`docs/modules/browser-extension.md`; purged references from README, docs, roadmap,
pricing/landing copy, and setup/test scripts; kept `POST /sources/detect` (used by
onboarding). This resolved 6 findings that were open against the extension (4 high, 2 low).

## WS9 — Reply-drafter prompt-injection sanitization ✅ DONE (2026-07-01)
The reply drafter can auto-send over SMTP, so the raw recruiter subject/body was the
highest-risk injection sink. Now both the stored `body_excerpt` **and** the subject are run
through `email_classifiers/sanitize.py` before they reach any drafter, and either matching
injection patterns bypasses the LLM entirely (heuristic drafts instead; flagged via
`injection_guarded` + a draft note). Detection runs on the sanitized text so HTML-encoded
payloads are caught.
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | Reply drafter fed **raw** recruiter subject+body into the LLM (this path can auto-send over SMTP). Now `sanitize_message_body` strips/caps both in `_build_context`, and `looks_like_prompt_injection` on either forces the offline heuristic (never the LLM) | `services/reply_drafts.py:91` | ✅ |
| ⚪ LOW | 📝 | Docs implied only the classifier guards injection; reply-drafter section now documents its sanitization + LLM-bypass-on-injection behavior | `docs/modules/inbox.md:338` | ✅ |
| ⚪ LOW | 🧪 | Added reply-draft regression tests: HTML-obfuscated body injection (pins sanitize-before-detect ordering), subject injection, and HTML-stripping on the clean path | `tests/services/test_reply_drafts.py` | ✅ |

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

## WS11 — Documentation updates ✅ DONE (2026-07-01)
(Doc rows also live under their subsystem above; these are the docs-cluster + infra items.)
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 📝 | `SCHEDULER_MAX_CATCHUP` is a dead setting — in config/.env/docs but never read. Deleted from `config.py`, `.env.example`, and terraform (occurrence the audit had missed); reworded worker.md + architecture.md to describe the recompute-from-now mechanism | `docs/modules/worker.md:32` | ✅ |
| ⚪ LOW | 📝 | 6 `config.py` Settings fields undocumented in `.env.example` (JWT_ALGORITHM + 5 dev-only inbox-AI tunables) | `.env.example:134` | ✅ |
| ⚪ LOW | 📝 | `SUMMARY_PROVIDER` comment omits shipped `anthropic` provider | `.env.example:93` | ✅ |
| ⚪ LOW | 📝 | `inbox.md` API table omits Outlook OAuth routes + `/reply-send-log` | `docs/modules/inbox.md:179` | ✅ |
| ⚪ LOW | 📝 | `scrapers.md` rate-limit table lists 13 of 17 adapters | `docs/modules/scrapers.md:95` | ✅ |
| ⚪ LOW | 📝 | `api.md` calls `/billing/checkout` Pro-only (accepts starter\|plus\|pro) | `docs/modules/api.md:84` | ✅ |
| ⚪ LOW | 📝 | `appliers.md`: undocumented Ashby `allow_unpublished_job_posting`; stale SmartRecruiters `consent`; Lever `compliance_policy_id`/`gdpr_consent` coupling | `docs/modules/appliers.md`, `appliers/adapters/lever.py:240` | ✅ |
| ⚪ LOW | 📝 | `catalog.py` docstring says edit `catalog_presets.py`, but ~40 employers now live in `presets/<id>.py` | `portals/catalog.py:4` | ✅ |

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

## WS13 — Password reset does not invalidate active sessions ✅ DONE (2026-07-01)
Surfaced by a later automated scan (Cursor, commit `5975194`), not the original audit.
Refresh tokens are stateless bearer JWTs with no server-side revocation, so
`reset_password` rotated only `password_hash` — a refresh token captured before recovery
(XSS on a non-browser API client, shared machine, network capture when
`AUTH_COOKIE_SECURE=false`, etc.) could be replayed via `POST /auth/refresh` to mint fresh
access tokens for up to `REFRESH_TOKEN_EXPIRE_DAYS` (7). Fix mirrors the existing
`feed_token_version` pattern: a `user.token_version` bumped on reset and embedded as a `ver`
claim in access+refresh tokens; `refresh` and `get_current_user` reject stale-`ver` tokens
(so reset also kills live access tokens, not just refresh). Deactivation already blocks
access via the `is_active` check, so it needs no separate bump.
| Sev | Type | Item | Location | Status |
| --- | ---- | ---- | -------- | ------ |
| 🟡 MED | 🔒 | `reset_password` updated only `password_hash`; a pre-reset refresh JWT still minted access tokens. Now bumps `token_version`, tokens carry `ver`, and `refresh`/`get_current_user` reject stale versions | `services/auth.py:130` | ✅ |

---

## Suggested PR sequencing (safest first)
1. **WS3** (security) + **WS11** (docs) — small, high value, low risk.
2. **WS1** (inbox UID overflow) + **WS2** (scheduler dup-notify) — correctness-critical.
3. **WS5** (billing) + **WS6** (scrapers) + **WS4** (apply adapters).
4. **WS7** (frontend) + **WS9** (reply-drafter sanitization).
5. **WS10** (LLM refactor) + **WS12** (test backfill) — larger, do last.

Each PR: `make check` green before/after; every bug fix ships a regression test that fails
before and passes after; docs updated in the same PR (Definition of Done, AGENTS.md §5).
