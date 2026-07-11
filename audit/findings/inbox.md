# Inbox — mailbox protocols, OAuth, classification, replies

This area covers the inbound-mail subsystem: mailbox protocol adapters (Gmail, Outlook, Yahoo, Fastmail/JMAP, IMAP), OAuth authorization/refresh, MIME parsing, message-to-job linking, the email classifier, the reply drafter, and the autonomous safe-send guardrails that gate auto-replies. The audit found no critical or high issues, but a consistent theme runs through the medium findings: the autonomous send path trusts data it should not. Provider-level send failures are reported as success, the auto-reply recipient and the LLM prompt inputs are unvalidated recruiter-controlled fields, a sensitive-topic safety regex misses the common spelling of "workers compensation," and OAuth refresh races can rotate a mailbox out of its own grant. The remaining low findings are sanitization/consistency divergences between the classifier and drafter, quota/N+1 perf gaps in polling, and unbounded input fields.

**Summary:** 0 critical · 0 high · 8 medium · 9 low (17 findings after merging 6 duplicate records).

---

<a id="inb-01"></a>
### INB-01 — Fastmail JMAP send/move report success on per-method errors (silent failed auto-send)
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/51)) · Confidence: high (5/5 verifiers) · Effort: S · WS30

_Merged with INB-02 (`fastmail_jmap.py:162`, same defect: JMAP method-level errors ignored on send/move)._

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/51): `raise_on_jmap_method_errors` runs inside `_call` for every method batch (method-level `error` rows and non-empty `notCreated`/`notUpdated`/`notDestroyed`), and `send_message` requires both `Email/set` and `EmailSubmission/set` to return `created` so a silent no-op cannot report success.

**Locations:** `backend/app/inbox/fastmail_jmap.py:246` (`FastmailJmapClient._call`); plus `backend/app/inbox/fastmail_jmap.py:139`, `backend/app/inbox/fastmail_jmap.py:162` (`send_message`), `backend/app/inbox/fastmail_jmap.py:181`, `backend/app/inbox/fastmail_jmap.py:202`, `backend/app/inbox/fastmail_jmap.py:231`, and the adapter at `backend/app/inbox/adapters/fastmail.py:56`.

**Evidence.** `_call` only calls `raise_for_status()` and checks that `methodResponses` is a list; it never inspects the per-method JMAP `error` response, `notCreated`, `notUpdated`, or `notDestroyed`. JMAP (RFC 8620 §3.6) reports method-level failures inside a **200 OK** body, so `send_message`/`move_message` return normally and the Fastmail adapter reports `status="sent"`/`"moved"`. Sibling adapters surface failures via `raise_for_status`/status checks.

**Failure scenario.** Fastmail rejects `Email/set` or `EmailSubmission/set` (bad identity, quota exceeded, blocked recipient) with HTTP 200 and a `notCreated`/error entry. The adapter returns `status="sent"`; `pending_replies.py:215` and `ghost_detection.py:90` mark the reply delivered with no retry. The recruiter auto-reply or ghost-archive move never actually happened, but the system believes it did.

**Suggested fix.** After `_call`, scan `methodResponses` for an `error` method name and for `notCreated`/`notUpdated`/`notDestroyed` on the relevant id (and confirm `Email/set` `created`); raise `ValueError` so the adapter maps it to `status="failed"` and the pipeline retries.

**Verification.** Confirmed 5/5 adversarial verifiers. `_call` (244-249) checks only HTTP status and list-ness; JMAP per-method errors arrive HTTP 200, so send/move return `None` and the adapter reports success for a failed op. Real but recoverable silent-fail; medium.

<a id="inb-03"></a>
### INB-03 — Auto-reply recipient is raw inbound From, not checked vs linked employer domain
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/48)) · Confidence: medium (3/3 verifiers) · Effort: S · WS29

**Update (2026-07-10).** Already fixed in `0135f08`: `ReplySafeSendService.evaluate_before_send` calls `auto_reply_recipient_allowed`, which requires the inbound `From` domain to match the linked application's `employer_domain` (or job URL host). Mismatches return `blocked_recipient` and never SMTP-send. Tracker/docs/regression aligned — [PR](https://github.com/davidcristian/HeadStart/pull/48).

**Locations:** `backend/app/inbox/reply_message.py:16` (`build_recruiter_reply_message`); plus `backend/app/services/pending_replies.py:207`, `backend/app/services/inbox_gate.py:63`.

**Evidence.** `to_addr = classification.from_addr.strip()` — the autonomous SMTP send targets whatever the inbound mail claimed as its `From`. The inbox gate admits messages via forged `References`/`In-Reply-To` headers or via an allowlist regardless of `From`, and nothing asserts that `from_addr` falls within the matched application's `employer_domain`.

**Failure scenario.** An attacker emails the mailbox `From: attacker@evil.com` with a forged `References` header naming a known outbound `Message-ID` (or matching an allowlist). The message is gated, classified `follow_up`, auto-drafted, and a reply containing profile PII is auto-sent to `attacker@evil.com`.

**Suggested fix.** Before auto-send, require the reply recipient's domain to equal (or be a subdomain of) the linked application's `employer_domain`; skip or queue-for-review otherwise.

**Verification.** Confirmed 3/3 adversarial verifiers. `reply_message.py:16` sends to `classification.from_addr` with no employer_domain binding and no upstream guard. Exploit is preconditioned (a private outbound Message-ID to forge References, or an allowlist entry, plus `auto_reply_enabled`); medium fits.

<a id="inb-04"></a>
### INB-04 — Sensitive-topic filter misses plain "workers compensation" (auto-reply guard bypass)
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/52)) · Confidence: certain (3/3 verifiers) · Effort: XS · WS30

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/52): `workers_comp` pattern is now `r"\bworkers['’]?\s*compensation\b"` so plain `workers compensation`, ASCII apostrophe, and curly-apostrophe forms all block auto-reply.

_Merged with INB-05 (exact duplicate record for the same regex bug at the same line)._

**Locations:** `backend/app/inbox/safe_send.py:26` (`SENSITIVE_TOPIC_PATTERNS`).

**Evidence.** The pattern is `r"\bworkers[' ] compensation\b"`. The char class `[' ]` matches exactly one of apostrophe-or-space, and it is immediately followed by a **literal space** — so the pattern demands two characters between the words. Verified with Python `re`: it matches `"workers' compensation"` but does **not** match the canonical single-space `"workers compensation"`.

```python
r"\bworkers[' ] compensation\b"
#           ^^^^ one char        ^ then a literal space  -> needs TWO chars
```

**Failure scenario.** A recruiter email or draft that says `workers compensation` (plain single space, the common spelling) is not flagged; `check_topic_blocklist` returns `None` and the autonomous auto-reply proceeds on a legally/HR-sensitive thread the guardrail was meant to block.

**Suggested fix.** Use `r"\bworkers['’]?\s*compensation\b"` (optional apostrophe plus `\s*`) so both `"workers compensation"` and `"workers' compensation"` match.

**Verification.** Confirmed 3/3 adversarial verifiers. Verified via `re`: `[' ]` plus a literal space needs two chars, so the common spelling bypasses this auto-send safety pattern.

<a id="inb-06"></a>
### INB-06 — Unlocked concurrent OAuth token refresh rotates Outlook/Yahoo token, breaks mailbox
🟡 **MEDIUM** · 🐞 bug · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/53)) · Confidence: high (5/5 verifiers) · Effort: M · WS30

_Merged with INB-19 (`inbox_oauth.py:63`, same TOCTOU refresh race; INB-19 was rated low, this record high — reported at the higher-verifier medium framing)._

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/53): near-expiry Gmail/Outlook/Yahoo refresh locks `mailbox_credential` (`SELECT … FOR UPDATE` on Postgres), re-decodes tokens under the lock, and skips the provider call when a peer already rotated the refresh_token.

**Locations:** `backend/app/services/inbox_oauth.py:63` (`ensure_fresh_outlook_config`); plus `backend/app/services/inbox_oauth.py:49`, `backend/app/services/inbox_oauth.py:77`, `backend/app/inbox/outlook_oauth.py:153`, `backend/app/inbox/yahoo_oauth.py:145`, `backend/app/repositories/mailbox_credentials.py:13`.

**Evidence.** `resolve_context` → `ensure_fresh_*_config` reads the stored config, POSTs the `refresh_token`, and persists the result with **no row lock** — `MailboxCredentialRepository` has no `with_for_update` (the digest path uses it elsewhere). `refresh_outlook`/`refresh_yahoo` persist a **rotated** `refresh_token`. Three beat tasks (inbox poll, ghost detection, pending replies) call `resolve_context` for the same user every tick, and the web `/inbox/messages` route also triggers it.

**Failure scenario.** Two tasks refresh a near-expiry Outlook/Yahoo token concurrently: the first rotates it, the second then POSTs the now-invalidated token; the provider revokes the grant and the mailbox disconnects until the user re-consents.

**Suggested fix.** Lock the `MailboxCredential` row (`SELECT ... FOR UPDATE`) before the needs-refresh check and refresh under the lock, re-checking expiry inside the transaction and persisting only when the token advanced — or serialize refresh per user.

**Verification.** Confirmed 5/5 adversarial verifiers. Genuine TOCTOU but a tight-timing race with recoverable (re-consent) impact, so medium.

<a id="inb-07"></a>
### INB-07 — Reply-drafter feeds raw inbound From into the LLM with no sanitize or injection guard
🟡 **MEDIUM** · 🔒 security · Status: ✅ done · Confidence: high (5/5 verifiers) · Effort: S · WS29

_Merged with INB-21 and INB-22 (all three flag the same gap: `inbound_from` bypasses `sanitize_message_body` and the `looks_like_prompt_injection` guard, then reaches the auto-send drafter LLM). INB-21/INB-22 were rated low; reported here at the highest-verifier medium framing._

**Locations:** `backend/app/services/reply_drafts.py:210` (`ReplyDraftService._build_context`); plus `backend/app/services/reply_drafts.py:92` (the injection guard), `backend/app/services/reply_drafts.py:209`, `backend/app/reply_drafters/prompts.py:29`/`:31`/`:33` (`- From: {inbound_from}`).

**Evidence.** `_build_context` sanitizes `inbound_body` and `inbound_subject` but sets `inbound_from = classification.from_addr` raw; `prompts.py` injects it into the prompt as `- From: {inbound_from}`. The injection check (lines 92-95) runs `looks_like_prompt_injection` only on `inbound_body`/`inbound_subject`, never on `inbound_from`. WS9 hardened subject and body but left `From` open.

**Failure scenario.** An attacker whose `From` address or display-name local-part carries injection tokens (e.g. `ignore-all-previous-instructions@x.com`) reaches this SMTP-auto-send-capable path unfiltered; WS9's guard, which forces the heuristic fallback on injection, is bypassed via the `From` field and can steer the drafted reply.

**Suggested fix.** Sanitize `inbound_from` and include it in the `looks_like_prompt_injection` check (or drop it from the prompt) so all recruiter-controlled fields are guarded, mirroring subject/body handling.

**Verification.** Confirmed 5/5 adversarial verifiers. `reply_drafts.py:209` uses `inbound_from=from_addr` raw (a parsed header, `String(320)`, not validated); the injection check covers only body/subject; `prompts.py` injects it, bypassing the WS9 guard on the auto-send path. The From surface is narrow (still bounded by rate/topic/human-review guards), so medium.

<a id="inb-08"></a>
### INB-08 — Safe-send topic blocklist scans raw, HTML-encoded, 500-char-truncated inbound body
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/54)) · Confidence: high (3/3 verifiers) · Effort: S · WS30

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/54): `_classification_payload` stores `sanitize_message_body(...)` up to `EMAIL_CLASSIFY_MAX_BODY_CHARS`, and `ReplySafeSendService._inbound_body` re-sanitizes with `max_chars=0` before `check_topic_blocklist`, so HTML-entity and late-in-body sensitive terms still block auto-replies.

**Locations:** `backend/app/services/reply_safe_send.py:153` (`ReplySafeSendService._inbound_body`); plus `backend/app/services/email_classification.py:56`, `backend/app/inbox/safe_send.py:38`.

**Evidence.** `_inbound_body` returns `payload["body_excerpt"]` verbatim; that excerpt is `message.body_text[:500]` with no `html.unescape` and no tag-stripping. `check_topic_blocklist` regexes then run on raw text — unlike the drafter, which calls `sanitize_message_body` first (`reply_drafts.py:190`).

**Failure scenario.** A lawsuit/harassment/severance thread that encodes the term (`&#108;awsuit`) or places it past character 500 evades the legal/HR blocklist; `check_topic_blocklist` returns nothing and HeadStart auto-sends a reply on a thread the guardrail should block.

**Suggested fix.** Run the topic blocklist over `html.unescape` + tag-stripped inbound text (reuse `sanitize_message_body`) across the full body, not the raw 500-char excerpt.

**Verification.** Confirmed 3/3 adversarial verifiers. `reply_drafts.py:190` sanitizes the body before drafting, but `reply_safe_send._inbound_body` returns the raw stored excerpt (unsanitized at `email_classification.py:56`) to `check_topic_blocklist`; HTML-entity or >500-char terms evade the guard.

<a id="inb-09"></a>
### INB-09 — Email classifier sends raw subject/From/To to the LLM with no injection guard
🟡 **MEDIUM** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/50)) · Confidence: high (3/3 verifiers) · Effort: S · WS29

**Update (2026-07-10).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/50): `prepare_message` sanitizes From/To/Subject via `sanitize_message_header`; `EmailClassificationService` forces the heuristic classifier when those headers or the body match injection patterns (payload records `injection_guarded`); heuristic haystack also covers From/To.

_Merged with INB-15 and INB-16 (all three flag that `prepare_message` sanitizes body only, and the classifier emits raw subject/From/To to the LLM with no `looks_like_prompt_injection` guard on the LLM adapters). INB-15/INB-16 were rated low; this record was rated low as a consistency finding — reported here as the security defect all three describe._

**Locations:** `backend/app/services/email_classification.py:175` (`EmailClassificationService._build_context`); plus `backend/app/email_classifiers/sanitize.py:36` (`prepare_message`), `backend/app/email_classifiers/prompts.py:29`/`:30`/`:34`, `backend/app/email_classifiers/adapters/heuristic.py:63`.

**Evidence.** `prepare_message` updates only `body_text` (`sanitize.py:38`); the classifier `user_prompt` emits raw `from_addr`, `to_addrs`, and `subject` into the prompt. Only the heuristic classifier calls `looks_like_prompt_injection` — the LLM adapters (openai/gemini/anthropic) never do. This diverges from `ReplyDraftService._build_context`, which sanitizes both subject and body before its LLM call.

**Failure scenario.** A crafted recruiter subject or `From` display name injects the classifier LLM to force a label (e.g. `interview_request`), triggering ghost-recovery/interview-handoff alerts and mis-routing. Label-set validation bounds the output but does not prevent a mislabel, which then feeds the auto-draft pipeline.

**Suggested fix.** Sanitize subject (and the From display name) in `prepare_message`/`_build_context` and run `looks_like_prompt_injection` on subject + body before the LLM classifier, mirroring `ReplyDraftService`.

**Verification.** Confirmed 3/3 adversarial verifiers. Output is bounded to the label set plus the system prompt, so impact is mislabel/mis-routing rather than a direct send; a real residual injection surface, medium is slightly generous but defensible given the downstream auto-draft coupling.

<a id="inb-10"></a>
### INB-10 — Gmail poll issues a metadata GET for every listed message (up to ~2000/poll)
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: M · WS30

**Locations:** `backend/app/inbox/adapters/gmail.py:213` (`GmailMailbox._list_unpolled_candidates`).

**Evidence.** The loop paginates up to `max_pages=20` with `page_size=max(limit*3, 100)`, calling `_message_received_at` (a separate `messages.get`) for **every** entry to derive the uid before the `[:limit]` slice. Each kept message then triggers a second full `get` via `_fetch_raw_message`.

**Failure scenario.** A busy inbox fans one poll out to ~20×100 metadata GETs plus a raw GET per kept message, burning Gmail per-user quota and slowing the worker; this violates the polite-scraper bar in AGENTS §7.

**Suggested fix.** Request `internalDate` in the `messages.list` batch, or short-circuit pagination once `limit` earliest candidates are collected, and cache `received_at` with the raw fetch.

**Verification.** Confirmed 3/3 adversarial verifiers. `_list_unpolled_candidates` calls `_message_received_at` for every listed entry before the `[:limit]` slice, then `_fetch_raw_message` per kept message; a real N+1/quota-burn perf issue, low as rated.

<a id="inb-11"></a>
### INB-11 — OAuth authorization-code flows omit PKCE across all three providers
⚪ **LOW** · 🔒 security · Status: ✅ done ([PR](https://github.com/davidcristian/HeadStart/pull/140)) · Confidence: medium (3/3 verifiers) · Effort: M · WS29

**Locations:** `backend/app/inbox/gmail_oauth.py:78` (`build_gmail_authorization_url`); plus `backend/app/inbox/outlook_oauth.py:81`, `backend/app/inbox/yahoo_oauth.py:75`.

**Evidence.** The auth URLs pass only `response_type`/`state` and no `code_challenge`; the `exchange_*_code` functions send no `code_verifier`. `state` is a signed JWT (good CSRF binding), but there is no PKCE. OAuth 2.1 / BCP recommend PKCE even for confidential clients to defend against auth-code interception at the redirect.

**Failure scenario.** If an authorization code leaks at the redirect (via `Referer`, logs, or an open-redirect on the callback host), PKCE would block replay; its absence weakens defense-in-depth on token acquisition for all mailbox connects.

**Suggested fix.** Generate a per-flow `code_verifier`, embed its S256 challenge in the auth URL, carry the verifier in the signed state, and send `code_verifier` on exchange.

**Verification.** Confirmed 3/3 adversarial verifiers. No `code_challenge` in the auth URLs and no `code_verifier` on exchange; PKCE is defense-in-depth for these confidential clients (state is already a signed JWT for CSRF), correctly rated low.

<a id="inb-12"></a>
### INB-12 — OAuth-config class list re-enumerated in 4+ sites instead of a shared constant
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: high (3/3 verifiers) · Effort: S · WS30

**Locations:** `backend/app/inbox/mailbox_email.py:16` (`mailbox_email_from_context`); plus `backend/app/inbox/mailbox_email.py:39`, `backend/app/inbox/credentials.py:20`, `backend/app/inbox/credentials.py:58`.

**Evidence.** The `{gmail, outlook, yahoo, fastmail}` connector set and the `(Gmail|Outlook|Yahoo|Fastmail)MailboxConfig` `isinstance` tuple are hand-listed in `mailbox_email.py` (twice) and `credentials.py`. A fifth OAuth connector requires editing every copy; a missed site mis-routes to the `imap_smtp` branch.

**Failure scenario.** A future OAuth connector added to the types/decode path but missed in one of these lists is treated as `imap_smtp` and raises `TypeError` ("requires MailboxConfig") at runtime for that connector.

**Suggested fix.** Define `OAUTH_CONNECTOR_TYPES` / `OAUTH_CONFIG_TYPES` once near `types.py`, import everywhere, and assert coverage in a test.

**Verification.** Confirmed 3/3 adversarial verifiers. The literal set and the `isinstance` tuple are hand-duplicated across four sites; a real DRY/maintainability low refactor finding.

<a id="inb-13"></a>
### INB-13 — extract_body_text returns empty for HTML-only multipart mail (no text/plain part)
⚪ **LOW** · 🐞 bug · Status: ✅ done · [PR](https://github.com/davidcristian/HeadStart/pull/141) · Confidence: medium (5/5 verifiers) · Effort: S · WS29

**Locations:** `backend/app/inbox/parse.py:24` (`extract_body_text`).

**Evidence.** `walk()` picks the first non-attachment `text/plain` part (matched at line 30); a `multipart/alternative` message carrying only `text/html` yields no match and returns `""`. That empty `body_text` then feeds classification and reply-draft context.

**Failure scenario.** A recruiter sends an HTML-only email (common) via IMAP/Yahoo/Gmail-raw → `body_text=""` → the classifier and reply-drafter operate on an empty body, degrading classification and reply quality.

**Suggested fix.** Fall back to stripping `text/html` to plain text when no `text/plain` part exists, matching typical mail-client behavior.

**Verification.** Confirmed 5/5 adversarial verifiers. `extract_body_text` matches only `text/plain` in multipart mail; an HTML-only `multipart/alternative` returns `""`, feeding an empty body downstream — a real low-severity correctness gap with no security impact.

<a id="inb-14"></a>
### INB-14 — Client-supplied InboxMessage fields (subject/body_text/raw_headers) have no bounds
⚪ **LOW** · 🔒 security · Status: ✅ done · Confidence: medium (3/3 verifiers) · Effort: S · WS29

**Locations:** `backend/app/inbox/types.py:74` (`InboxMessage`).

**Evidence.** `InboxMessage.subject`/`body_text`/`from_addr` default to `""` with no `max_length`, and `raw_headers: dict[str, str]` / `to_addrs` carry no max-items caps — unlike `OutboundMessage`, whose fields are bounded. `InboxMessage` is accepted directly from the client via `EmailClassifyRequest.message` on `POST /inbox/classify` and feeds the classifier/reply-drafter (a path that can auto-send SMTP per WS9).

**Failure scenario.** An authenticated inbox user POSTs `/inbox/classify` with a multi-MB `body_text` or thousands of `raw_headers`, producing an unbounded LLM prompt and storage load on a dev-gated but reachable path.

**Suggested fix.** Cap `subject`/`from_addr`/`body_text` `max_length` and `raw_headers`/`to_addrs` item counts on the API-facing `InboxMessage`, matching `OutboundMessage`'s bounded fields.

**Verification.** Confirmed 3/3 adversarial verifiers. `InboxMessage` fields are plain `str` with no `max_length` and its collections have no item caps, unlike `OutboundMessage`; accepted from the client with no upstream bound — a genuine low input-bounds gap.

**Update (2026-07-11).** Fixed in [PR](https://github.com/davidcristian/HeadStart/pull/142): `InboxMessage` Field bounds + validators; RFC822/JMAP parsers clip oversized fields before construct; classify API returns 422 on oversize client payloads.

<a id="inb-17"></a>
### INB-17 — score_job_match compares In-Reply-To to outbound ids without normalization
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: XS · WS29

**Locations:** `backend/app/services/inbox_linking.py:56` (`score_job_match`); plus `backend/app/services/inbox_gate.py:109`, `backend/app/services/inbox_gate.py:129`.

**Evidence.** `message.in_reply_to in outbound_ids` compares raw strings, whereas the gate normalizes both sides via `normalize_message_id` before membership tests (`inbox_gate.py:109`/`:129`). Stored-id or header whitespace differences silently miss the `+80` boost.

**Failure scenario.** A genuine recruiter reply whose `In-Reply-To` differs only by whitespace from the stored outbound id loses the strong-signal boost and may mis-link or fail to link to the right application.

**Suggested fix.** Normalize both `message.in_reply_to` and each outbound id with `normalize_message_id` before comparison, matching the gate.

**Verification.** Confirmed 3/3 adversarial verifiers. `score_job_match` compares raw `in_reply_to` against un-stripped payload ids while the gate strips both sides; whitespace diffs miss the boost. The bracket claim in the original evidence is overstated (`normalize` only strips), but a genuine low consistency delta.

<a id="inb-18"></a>
### INB-18 — Message-to-job linking accepts a bare company-name substring as confident match
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: S · WS29

**Locations:** `backend/app/services/inbox_linking.py:71` (`link_message_to_job`); plus `backend/app/services/inbox_linking.py:51`.

**Evidence.** A threshold of `best_score >= 20` returns a match, and a company-name substring alone adds exactly `20` (`len(company) > 2 and company in haystack`). No domain or thread corroboration is required for a "confident" link.

**Failure scenario.** An unrelated email mentioning a common company name (Meta, Apple) links to that application, mis-attributing the thread and — with auto-reply on — potentially replying to a non-recruiter sender.

**Suggested fix.** Raise the threshold or require a corroborating signal (domain/thread) in addition to a company/title substring before linking.

**Verification.** Confirmed 3/3 adversarial verifiers. The substring adds exactly 20 and the threshold is `>=20`; the gate's `should_process` blocks off-domain senders so the reply-to-stranger scenario is largely mitigated, but wrong-application mis-attribution among the user's own gated apps is real, low.

<a id="inb-20"></a>
### INB-20 — Inbox poll resolves each user's mailbox context twice per beat tick (N+1)
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: S · WS30

**Locations:** `backend/app/services/inbox_orchestration.py:97` (`_list_pollable_user_ids`); plus `backend/app/services/inbox_orchestration.py:104`, `backend/app/services/inbox_orchestration.py:109`.

**Evidence.** When `inbox_use_env_credentials` is on, `_list_pollable_user_ids` iterates `users.list_all()` calling `resolve_context(user.id)` for each; then `_process_user` calls `resolve_context(user_id)` again per user. `resolve_context` does its own credential/config lookups (and token refresh), so this is O(users) DB work performed twice.

**Failure scenario.** With env-credential mode enabled and many accounts, each inbox beat tick resolves every user's mailbox context twice, running redundant per-user credential/config queries that scale with total user count rather than pollable count.

**Suggested fix.** Resolve each user's context once, cache/pass it into `_process_user`, and batch-load the enabled-credential + config rows instead of resolving per user.

**Verification.** Confirmed 5/5 adversarial verifiers. With `inbox_use_env_credentials` on, `resolve_context` runs once per user in `_list_pollable_user_ids` (l104) and again per pollable user in `_process_user` (l109); redundant queries in that mode, correctly rated low perf.

<a id="inb-23"></a>
### INB-23 — Auto-reply rate caps are check-then-act with no lock; overlap can exceed the cap
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/3 verifiers) · Effort: M · WS30

**Locations:** `backend/app/services/reply_safe_send.py:80` (`ReplySafeSendService.evaluate_before_send`); plus `backend/app/services/pending_replies.py:185`.

**Evidence.** `evaluate_before_send` reads `count_sent_since` (lines 82, 95) and only later does `record()` write the `sent` log; no lock spans read → send → record, and `list_due` uses no `SKIP LOCKED`/lease. Two concurrent pending replies for one user can each read the same below-cap count and both send.

**Failure scenario.** With overlapping `process_pending_replies` ticks and multiple due rows for one user, the configured `inbox_reply_max_per_hour`/`per_day` guardrail is exceeded by the number of concurrent senders.

**Suggested fix.** Serialize the send pass per user (or reserve a send slot atomically before SMTP), alongside a `list_due` lease fix.

**Verification.** Confirmed 3/3 adversarial verifiers. `evaluate_before_send` reads the count then `record()` writes later with no lock, and `list_due` has no `SKIP LOCKED`, so concurrent workers can both read below-cap and both send; requires concurrent ticks + multiple due rows and is recoverable — low is fair.
