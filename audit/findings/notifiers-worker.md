# Notifiers, Celery worker & scheduler, CLI

This area covers the notification adapters (Slack, Discord, Telegram, ntfy, webhook, email), the digest formatting/delivery pipeline, the Celery worker/beat scheduler configuration, and the CLI seed command. The headline: no critical or high findings, but there is a coherent cluster of **auto-apply reliability defects** — `acks_late` is enabled with no time limits, no `task_reject_on_worker_lost`, and a non-idempotent live submit, so a worker crash or commit failure can double-submit a real job application to an employer. Alongside that, two medium **secret-leak / injection** issues affect notifiers (Telegram bot token persisted via `str(HTTPError)`; unescaped scraped fields injected into Slack/Discord markup), plus a tail of low-severity hardening gaps (guessable default ntfy topic, URL-in-error leaks, header override, Celery result/time-limit hygiene, and English-only user-facing copy).

**Summary:** 0 critical · 0 high · 6 medium · 6 low (12 findings after merges; 14 source records).

---

<a id="ntf-03"></a>
### NTF-03 — acks_late set but no task time limit / reject-on-worker-lost; non-idempotent live apply can double-submit
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/18)) · Confidence: high (5/5 verifiers) · Effort: M · WS15

> Merged from NTF-03 (uid 144), NTF-04 (uid 149) and NTF-05 (uid 264): three records describing the same defect cluster — `acks_late` redelivery plus a non-idempotent live submit that shares the outer transaction — from the worker-config, broker-behavior, and commit-failure angles respectively.

**Locations:** `backend/app/worker/celery_app.py:19` / `:25` (`celery_app.conf.update`); plus `backend/app/worker/tasks.py:83`, `:94` (`apply_to_job_task`), `backend/app/services/apply.py:117`, `:136`, `:155`.

**Evidence.** `celery_app.conf.update` sets `task_acks_late=True` but omits `task_time_limit`, `task_soft_time_limit`, and `task_reject_on_worker_lost`. `apply_to_job_task` runs with `max_retries=0` and is non-idempotent: the `processing` status flip (apply.py:121) and the live external submit (apply.py:136) share one `session_scope` transaction that only commits at scope exit, so the flip is not durable before the external POST. The only re-apply guard is `get_pending_for_job`, which blocks on `queued`/`processing` status only.

**Failure scenario.** Two concrete paths. (1) Worker is SIGKILL/OOM-killed mid-`apply_to_job` after the external POST but before commit: the transaction rolls back so the row still reads `queued`, `acks_late` (with no `task_reject_on_worker_lost`) redelivers the message, the guard at apply.py:119 passes, and the application is submitted to the employer a second time. (2) External site accepts the application, then the DB commit fails: the except-branch `fail_queued_apply` marks the log `failed` and rolls `job.status` back, so a subsequent user re-apply is no longer blocked and duplicates the live submission. Separately, with no time limit a hung task holds the acked-late message indefinitely.

**Suggested fix.** Set `task_time_limit`/`task_soft_time_limit` and `result_expires`; add `task_reject_on_worker_lost`; commit an in-flight/idempotency marker (e.g. `external_application_id`) before the external call so redelivery and re-apply both detect a prior success and cannot double-submit.

**Verification.** Confirmed 5/5 (NTF-03), 5/5 (NTF-04) and 3/3 (NTF-05) adversarial verifiers. `session_scope` commits only at scope exit, so the processing flip isn't durable before the live POST; on SIGKILL, `acks_late` without `task_reject_on_worker_lost` redelivers and the row still reads `queued`, passing the guard — a double live apply, plus no time-limit protection for hangs.

<a id="ntf-01"></a>
### NTF-01 — Unescaped scraped fields in Slack mrkdwn / Discord markdown -> phishing links
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/55)) · Confidence: high (5/5 verifiers) · Effort: S · WS31

**Locations:** `backend/app/notifiers/adapters/slack.py:108` (`SlackNotifier._text` / `_digest_payload`); plus `backend/app/notifiers/adapters/slack.py:94`, `backend/app/notifiers/adapters/discord.py:82`, `backend/app/notifiers/adapters/discord.py:107`.

**Evidence.** Slack builds `<{job.url}|Apply>` and mrkdwn from raw `job.title`/`summary`/`url`, and Discord builds `[{headline}]({url})` — all from scraper-normalized fields sourced from untrusted third-party HTML/JSON, with no escaping. Telegram (telegram.py:95) `html.escape`s its fields; Slack and Discord are the outliers.

**Failure scenario.** A poisoned posting whose title/summary is `<https://evil.tld|Click>` (or a URL crafted to break out of the anchor) renders an attacker-controlled clickable link inside the user's Slack/Discord digest — phishing delivered inside a channel the user trusts.

**Suggested fix.** Escape Slack special characters (`<`, `>`, `&`) and strip markdown link syntax from Discord text; build the `href` only from a validated `job.url`.

**Verification.** Confirmed 5/5 adversarial verifiers. Slack `_text`/`_digest` build mrkdwn `<url|Apply>` and Discord builds `[headline](url)` from unescaped scraper fields (JobPosting has no sanitization) while telegram.py escapes — a poisoned posting can inject attacker-controlled clickable links into a trusted channel. Real medium injection.

<a id="ntf-02"></a>
### NTF-02 — Telegram bot token leaked into persisted DeliveryLog.error and logs via str(HTTPError)
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/56)) · Confidence: high (5/5 verifiers) · Effort: S · WS31

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/56): `_safe_http_error` replaces the bot token in `str(httpx.HTTPError)` before warning logs and `DeliveryResult.error` on both immediate and digest sends.

**Locations:** `backend/app/notifiers/adapters/telegram.py:70` (`TelegramNotifier._send_digest` / `_send_one`); plus `backend/app/notifiers/adapters/telegram.py:82`, `backend/app/services/pipeline.py:271`, `backend/app/services/digest.py:104`.

**Evidence.** The request URL is `f"{_TELEGRAM_API}/bot{token}/sendMessage"` (telegram.py:47). On failure the adapter sets `error=str(exc)` for an `httpx.HTTPError`, and `str()` of an httpx error includes the request URL — i.e. the bot token embedded in the path. That string is persisted to `DeliveryLog.error` (pipeline.py:271) and written to stdout logs (telegram.py:68/81).

**Failure scenario.** The Telegram API returns a 4xx/5xx or a connection error; `str(exc)` then contains `.../bot<SECRET_TOKEN>/sendMessage`, so the bot token is written into `delivery_log` (readable by admins/exports) and to logs.

**Suggested fix.** Redact the token before logging/persisting — build a masked URL for error messages, or strip the token from the httpx error; never store raw error strings for notifiers that carry the token in the URL.

**Verification.** Confirmed 5/5 adversarial verifiers. `str(httpx.HTTPStatusError)` includes the full bot-token URL; it is persisted to `DeliveryLog.error` (pipeline.py:271) and logged (l68/81), exposing the user's own bot token to logs and at-rest DB — a real leak, but scoped to the single user's own credential, hence medium not high.

---

<a id="ntf-06"></a>
### NTF-06 — Default ntfy topic 'headstart-change-me' is a guessable public channel with no entropy requirement, leaking PII
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS31

> Merged from NTF-06 (uid 147) and NTF-07 (uid 152): duplicate records for the same seeded default ntfy topic / missing entropy enforcement.

**Locations:** `backend/app/cli/seed.py:61` / `:62` (`seed`); plus `backend/app/core/config.py:167`, `backend/app/notifiers/adapters/ntfy.py:44`.

**Evidence.** `seed` writes `ntfy_default_topic='headstart-change-me'` (config.py:167) into a live notification target. The ntfy adapter (ntfy.py:44) requires only a non-empty `topic`, and no entropy check exists anywhere in the schema or service. On ntfy.sh the topic name *is* the capability: anyone who knows it can both read all pushes and publish to it. The only safety is that the seeded search is created disabled.

**Failure scenario.** A user enables a search without changing the guessable default topic. Every job notification (summaries and other PII) is then readable by anyone who guesses `headstart-change-me` on public ntfy.sh, and that party can also spam-push arbitrary messages to the user.

**Suggested fix.** Reject placeholder / low-entropy topics in the schema/service; generate a random high-entropy default in `seed`; warn users that ntfy topics are secrets and recommend an auth token.

**Verification.** Confirmed 3/3 (NTF-06) and 3/3 (NTF-07) adversarial verifiers. The ntfy adapter requires only a non-empty topic with no entropy check; seed writes the guessable `headstart-change-me`; on ntfy.sh the topic is the sole access control, so enabling without changing it leaks PII. Low is fair given it relies on the user ignoring the "change-me" default.

<a id="ntf-08"></a>
### NTF-08 — Scraped, unvalidated job URLs embedded unescaped into Slack/Discord markup links
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: S · WS31

> Related to NTF-01: NTF-01 covers escaping of the title/summary/URL text into Slack/Discord markup; this finding narrows in on the absence of `http(s)` scheme validation on `JobPosting.url` itself. Fixing both together (validate at ingest, escape at render) is the intended remediation.

**Locations:** `backend/app/notifiers/adapters/slack.py:118` (`SlackNotifier._text`); plus `backend/app/notifiers/adapters/discord.py:112`, `backend/app/scrapers/types.py:19`.

**Evidence.** `JobPosting.url` is a bare `str` with no scheme validation (scrapers/types.py:19; url normalization does not reject non-http schemes). Slack builds `<{url}|Apply>` (slack.py:118, :101) and Discord `[{headline}]({url})` (discord.py:112) with no escaping and no `http(s)` check. Telegram `html.escape`s its href (telegram.py:106); Slack and Discord are the outliers.

**Failure scenario.** A hostile scraper source returns a URL containing `|` or `>` (garbling the Slack link) or using a non-http scheme; the notifier renders an attacker-controlled "Apply" link that users trust and click.

**Suggested fix.** Validate that `JobPosting.url` is `http(s)` at ingest, and escape link metacharacters before interpolation, matching Telegram's handling.

**Verification.** Confirmed 5/5 adversarial verifiers. `JobPosting.url` is a bare `str` with no scheme check; Slack builds `<{url}|Apply>` and Discord `[...]({url})` unescaped while Telegram escapes — real but gated on a hostile scraper source, hence low.

<a id="ntf-09"></a>
### NTF-09 — Webhook notifier user headers can override Content-Type / base headers
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: XS · WS31

**Locations:** `backend/app/notifiers/adapters/webhook.py:116` (`_request_headers`).

**Evidence.** `_request_headers` seeds `{'Content-Type': 'application/json'}` and then loops over `config['headers']` adding `str(key): str(value)`, so a user-supplied `Content-Type` key overwrites the JSON content type. The HMAC signature header is added last, so it stays safe from override.

**Failure scenario.** A target configured with a `Content-Type` (or other base) header override changes the declared content type, mislabeling the JSON body to the receiver. Minor, and limited to the user's own webhook target.

**Suggested fix.** Reserve/skip base and signature header names when merging user headers, or apply user headers before the base headers so the base wins.

**Verification.** Confirmed 3/3 adversarial verifiers. `_request_headers` seeds `Content-Type` then user headers overwrite it via `headers[str(key)] = str(value)`; the signature added last stays safe; impact limited to the user's own webhook target, so low is fair.

<a id="ntf-10"></a>
### NTF-10 — User webhook/slack/ntfy URLs (may embed secrets) persisted into DeliveryResult.error via str(HTTPError)
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: S · WS31

> Merged from NTF-10 (uid 252) and NTF-11 (uid 329): both describe `error=str(exc)` on `httpx.HTTPError` embedding the full request URL — NTF-11 is the correct roll-up across all four HTTP notifiers, NTF-10 the webhook/ntfy-specific instance. (Distinct from NTF-02, which is the Telegram bot token specifically and rated medium.)

**Locations:** `backend/app/notifiers/adapters/webhook.py:79` / `:89` / `:90` (`WebhookNotifier._send_digest` / `_send_one`); plus `backend/app/notifiers/adapters/ntfy.py:88`, `:114`, `backend/app/notifiers/adapters/slack.py:66`, `backend/app/notifiers/adapters/discord.py:68`, `backend/app/services/pipeline.py:271` (persist).

**Evidence.** All HTTP notifiers set `error=str(exc)` for `httpx.HTTPError`, and `str()` of an httpx error embeds the full request URL — a user-supplied webhook/slack/discord/ntfy endpoint that often carries a secret path/token (Slack token, ntfy topic/auth). `pipeline.py:271` persists that string to `delivery_log.error`, and it is surfaced via `DeliveryFailureRead.error` back to the same user and into logs.

**Failure scenario.** A webhook/ntfy/slack target whose URL embeds a secret returns an HTTP error; the full URL including the secret is stored in `delivery_log` and displayed in app/admin delivery-failure views and logs.

**Suggested fix.** Strip/redact URLs (or store only `status_code` + reason) when persisting notifier errors instead of raw httpx error strings; prefer header auth over token-in-URL.

**Verification.** Confirmed 5/5 (NTF-10) and 5/5 (NTF-11) adversarial verifiers. `str(httpx.HTTPStatusError)` embedding the full request URL was reproduced; it is persisted to `delivery_log.error` (pipeline.py:267/271) and surfaced to the same user plus logs. Self-tenant scope (the user's own secret), hence low.

<a id="ntf-12"></a>
### NTF-12 — User-facing notification and email copy is hardcoded English with no localization hook
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: L · WS41

**Locations:** `backend/app/notifiers/digest_format.py:17` (`digest_title`); plus `backend/app/notifiers/adapters/email.py:86`, `:47`, `backend/app/core/email.py:41`, `:61`.

**Evidence.** All delivered strings are English literals: `digest_title` `'{count} new job(s)'`, the email body `'Why this matches:'` / `'Company:'` / `'Apply:'`, and the auth email subjects `'Reset your HeadStart password'` / `'Verify your HeadStart email'`. There is no locale parameter and no message catalog anywhere in the backend.

**Failure scenario.** A German user of the DE-branded instance receives English notification subjects, digest bodies, and password-reset / verification emails despite the German legal framing of the product.

**Suggested fix.** Introduce a per-user locale and a message catalog; parameterize notifier/email copy instead of inlining English literals.

**Verification.** Confirmed 5/5 adversarial verifiers. All cited strings are English literals (`digest_title`, email subjects/body) with no gettext/babel/locale mechanism anywhere in the backend — a genuine i18n gap, low.

<a id="ntf-13"></a>
### NTF-13 — No task_time_limit; a hung Playwright scrape holds a worker slot indefinitely
⚪ **LOW** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/18)) · Confidence: high (3/3 verifiers) · Effort: S · WS15

> Related to NTF-03 (which also flags the missing time limit as part of the auto-apply cluster); this record isolates the scrape-side worker-starvation impact of the same missing config.

**Locations:** `backend/app/worker/celery_app.py:19` (`celery_app.conf.update`).

**Evidence.** `conf.update` omits both `task_time_limit` and `task_soft_time_limit`. `run_search` drives Playwright/httpx scrapes with per-request timeouts only, giving no task-level deadline. `worker_prefetch_multiplier` is unset (default 4), so a long task head-of-line-blocks its prefetched siblings.

**Failure scenario.** A source that stalls past the httpx timeout (a drip response or a wedged Playwright page) ties up a worker child until `max_tasks_per_child` forces a restart, delaying other due searches.

**Suggested fix.** Set a hard `task_time_limit` and a shorter `task_soft_time_limit`; consider `worker_prefetch_multiplier=1` for these long, uneven tasks.

**Verification.** Confirmed 3/3 adversarial verifiers. `conf.update` (lines 19–30) omits `task_time_limit`/`task_soft_time_limit` and prefetch tuning; a stalled scrape holds a worker child until a `max_tasks_per_child` restart. A real hardening gap, low is fair.

<a id="ntf-14"></a>
### NTF-14 — Result backend enabled with no result_expires; unread task results accumulate in Redis
⚪ **LOW** · ⚡ perf · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/18)) · Confidence: high (2/3 verifiers) · Effort: XS · WS15

**Locations:** `backend/app/worker/celery_app.py:16` (`backend=settings.result_backend`); plus `backend/app/core/config.py:274`, `backend/app/worker/tasks.py:53`, `:129`.

**Evidence.** The result backend is set to `redis://.../1` (config.py:274), but `conf.update` never sets `result_expires` or `task_ignore_result`. Every `run_search`/apply/digest task returns a dict (tasks.py:53, :129) that is stored even though no code reads it, and the 30s beat cadence keeps writing new results.

**Failure scenario.** High-frequency beat ticks plus per-search results steadily fill Redis DB 1 with result payloads that nobody fetches, wasting memory on the shared broker/result Redis.

**Suggested fix.** Set a small `result_expires`, or use `task_ignore_result` / disable the backend for these fire-and-forget tasks.

**Verification.** Confirmed 2/3 adversarial verifiers (1 refuted). The result backend is set (config.py:275) but `conf.update` sets no `result_expires`/`task_ignore_result`; tasks return dicts nobody reads, accumulating in Redis DB 1. Confirmed, low is fair.
