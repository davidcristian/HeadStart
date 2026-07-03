# Auth, sessions, crypto, core platform, config

This area covers authentication and session management (login, registration, password reset, email verification, JWTs, feed tokens), credential encryption at rest (Fernet), GDPR account lifecycle (export and deletion), the core platform (config validation, logging, metrics, outbound-URL SSRF guard, request metadata) and HTTP hardening (security headers, OpenAPI exposure). The headline: the auth surface has **no rate limiting, no security event logging, and several enumeration vectors**, credential-at-rest encryption uses a weak unsalted KDF with no rotation path, GDPR deletion leaves live Stripe subscriptions and OAuth grants while the export is incomplete, and the password-reset path can leak secret tokens to logs when SMTP is misconfigured. A long tail of defense-in-depth gaps (missing security headers, spoofable audit IPs, JWT claim requirements, public docs) rounds out the picture. No critical-severity issues survived verification.

**Summary:** 🔴 critical: 0 · 🟠 high: 2 · 🟡 medium: 6 · ⚪ low: 15 (after merging 12 duplicate/systemic records into their canonical findings).

---

<a id="aut-01"></a>
### AUT-01 — Reset & verify tokens logged in plaintext when SMTP unset (no prod guard)
🟠 **HIGH** · 🔒 security · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS18

**Locations:** `backend/app/core/email.py:88` (`_send_or_log_email`); plus `backend/app/core/config.py:67`, `backend/app/core/email.py:38`.

**Evidence.** `_send_or_log_email` catches `SmtpNotConfiguredError` and does `logger.info("...link for %s: %s", to_email, log_url)`, emitting the full reset/verify URL with the secret token embedded. `smtp_host` defaults to `""` and, unlike `jwt_secret` which is gated in the same config module, no validator requires it outside local/test — so a production deployment that forgets to set SMTP will silently fall into the logging branch.

**Failure scenario.** A prod deploy that forgets to set `SMTP_HOST` silently logs every password-reset and email-verify URL (token embedded) to stdout; anyone with log-aggregator access mints a reset and takes over the account.

**Suggested fix.** Only log the URL when environment is local/test; in prod raise/alert on `SmtpNotConfiguredError`, or require `SMTP_HOST` via a `model_validator` when the environment is non-local.

**Verification.** Confirmed 5/5 adversarial verifiers. `_send_or_log_email` (email.py:88) logs the full reset/verify URL unconditionally on `SmtpNotConfiguredError`; `smtp_host` defaults to `''` with no validator gating it outside local/test, unlike `jwt_secret`. Token-in-logs enabling takeover rounds up to high.

<a id="aut-02"></a>
### AUT-02 — Account deletion never cancels Stripe subscription or deletes Stripe customer
🟠 **HIGH** · 🐞 bug · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: M · WS18

**Locations:** `backend/app/services/auth_account.py:70` (`delete_user_account`).

**Evidence.** `delete_user_account` only calls `repo.delete(user)`; there is no Stripe import or cancel. `billing.py` has `_ensure_customer`/subscription flows but no delete path. The `user.stripe_customer_id`/`stripe_subscription_id` values are dropped locally on deletion, orphaning the Stripe customer.

**Failure scenario.** A user with an active subscription deletes their account; Stripe keeps billing PII (name/email/card/invoices) and the subscription keeps charging the card with no local record to reconcile or refund.

**Suggested fix.** On deletion, cancel the Stripe subscription and delete/anonymize the Stripe customer; log the outcome. Handle Stripe errors without blocking local deletion.

**Verification.** Confirmed 5/5 adversarial verifiers. `delete_user_account` (auth_account.py:70) only records an audit row + `repo.delete(user)`; no Stripe cancel/delete though `billing.py` stores Stripe IDs on the user; the subscription keeps charging and Stripe retains PII. GDPR Art.17 + money-loss = high.

---

<a id="aut-03"></a>
### AUT-03 — No rate limiting on auth endpoints (login / register / forgot-password / reset / verify / resend)
🟡 **MEDIUM** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: M · WS19

**Merge note.** This consolidates three near-identical confirmed records — AUT-03 (uid 11), AUT-04 (uid 239) and AUT-09 (uid 15) — all reporting the same systemic absence of throttling across the auth surface.

**Locations:** `backend/app/api/v1/auth.py:64` (`login`); plus `backend/app/api/v1/auth.py:93` (`forgot_password`), `:100`/`:107`/`:113` (`reset_password`/`verify_email`/`resend-verification`), `:58` (`register`), `backend/app/main.py:28` (`create_app`), `frontend/nginx.conf:1`.

**Evidence.** A grep for `rate_limit`/`slowapi`/`Limiter`/`429`/`limit_req` across `backend/app`, `pyproject.toml`, `nginx.conf` and the terraform found no throttling anywhere. `create_app` registers only CORS middleware; there is no `slowapi`/`limits` dependency and `nginx.conf` serves static assets only (it proxies no `/api`). `login` runs one bcrypt per request as the only brake; reset/verify accept unlimited token guesses; forgot-password and resend-verification send SMTP synchronously and can be spammed.

**Failure scenario.** An attacker runs unlimited credential-stuffing against `POST /auth/login`, mass-guesses reset/verify tokens, or floods `/auth/forgot-password` and `/auth/resend-verification` to email-bomb arbitrary addresses and enumerate accounts — with no server-side throttle or lockout.

**Suggested fix.** Add per-IP + per-account rate limiting and backoff (slowapi/redis token bucket, or an infra WAF/`limit_req` rule) on login, register, forgot-password, reset-password, verify-email, resend-verification and refresh; cap outbound reset/verify email issuance per address per hour.

**Verification.** Confirmed 3/3 adversarial verifiers (each of the three merged records independently confirmed 3/3). No slowapi/limiter/`limit_req`/WAF anywhere; auth routes are unauthenticated and unthrottled, enabling brute-force and email-bombing. Verifiers flagged uid 11/15/239 as near-duplicates of one another.

<a id="aut-05"></a>
### AUT-05 — Fernet key: unsalted single SHA-256 derivation, no KDF, no key-rotation path
🟡 **MEDIUM** · 🔒 security · Status: ☐ open · Confidence: medium (5/5 verifiers) · Effort: M · WS19

**Merge note.** Merges the lower-severity duplicate AUT-14 (uid 251, low) into this canonical medium finding — same unsalted-SHA-256 KDF defect; AUT-05 additionally covers the missing rotation path.

**Locations:** `backend/app/core/crypto.py:22` (`_derive_key`); plus `backend/app/core/crypto.py:25`/`:29` (`_fernet`), `backend/app/core/config.py:77`.

**Evidence.** `_derive_key` does `urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())` — a fast, unsalted, single-round hash used directly as the Fernet key, with no PBKDF2/scrypt/argon2. The docstring explicitly invites "any human-friendly string." `_fernet()` returns one `lru_cached` Fernet with no `MultiFernet`, so rotating `credentials_secret_key` makes all existing ciphertext raise `InvalidToken`. The prod secret policy only rejects the literal placeholder string, not a weak/low-entropy custom key, and there is no minimum-length validator.

**Failure scenario.** An operator sets a low-entropy `CREDENTIALS_SECRET_KEY` (permitted by the docstring and policy); an attacker with DB read access brute-forces the key offline (no KDF, no salt) and decrypts all site/mailbox/OAuth credentials. Separately, rotating the key bricks every saved credential because there is no re-encrypt path.

**Suggested fix.** Require a Fernet-strength key (or stretch the secret via scrypt/PBKDF2/argon2 with a deployment salt); support `MultiFernet` with primary + legacy keys to enable rotation and re-encryption.

**Verification.** Confirmed 5/5 adversarial verifiers (the merged low duplicate confirmed 3/3). `_derive_key` is an unsalted single SHA-256 and there is a single Fernet with no rotation; `secret_policy` rejects only the exact placeholder, so a low-entropy key passes yet is brute-forceable. Hardening with no proven exploit, so medium is the ceiling.

<a id="aut-06"></a>
### AUT-06 — Worker /metrics HTTP server exposes Prometheus data unauthenticated on all interfaces
🟡 **MEDIUM** · 🔒 security · Status: ☐ open · Confidence: high (5/5 verifiers) · Effort: S · WS21

**Merge note.** Merges AUT-07 (uid 325, medium) — the same worker-metrics-ignores-METRICS_TOKEN defect, reported against the adjacent line.

**Locations:** `backend/app/core/metrics.py:102` (`start_metrics_server`, also cited at `:96`); plus `backend/app/worker/celery_app.py:36`, `backend/app/main.py:49`.

**Evidence.** `start_metrics_server` calls `prometheus_client.start_http_server(port)` with no `addr` and no auth (default addr `0.0.0.0`). Unlike the API's `/metrics` (main.py:49-53) which enforces `metrics_token` via `hmac.compare_digest`, the worker endpoint ignores `metrics_token` entirely and is fully unauthenticated. The metrics docs (metrics.md:56) imply the token protects both endpoints.

**Failure scenario.** An operator sets `METRICS_TOKEN` believing both surfaces are protected; anyone who can reach the worker's `metrics_port` (9090) scrapes internal pipeline/scrape/notification/delivery counters with no token.

**Suggested fix.** Bind the worker exporter to `127.0.0.1` and/or front it with the same `metrics_token` check used by the API; do not expose it unauthenticated on `0.0.0.0`. Document that bare `start_http_server` is unauthenticated.

**Verification.** Confirmed 5/5 adversarial verifiers (merged duplicate 3/3). The worker `start_metrics_server` binds `0.0.0.0` with no token while API `/metrics` enforces `metrics_token` via `hmac.compare_digest`; asymmetry confirmed. Low-sensitivity counter leak needing port reachability, so medium is the ceiling.

<a id="aut-08"></a>
### AUT-08 — SSRF guard resolves DNS then lets httpx re-resolve — DNS-rebinding TOCTOU bypass
🟡 **MEDIUM** · 🔒 security · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: L · WS21

**Locations:** `backend/app/core/outbound_url.py:55` (`assert_safe_outbound_url`); plus `backend/app/scrapers/http.py:41`/`:46`.

**Evidence.** `assert_safe_outbound_url()` runs `socket.getaddrinfo(host)` and IP-checks the result, but the actual `httpx.Client(follow_redirects=True)` performs a *fresh* DNS lookup at connect time with no pinned resolver. The validated addrinfo and the connected address can differ; the request event hook only re-checks the URL string, not the resolved peer.

**Failure scenario.** An attacker sets a user source/notifier URL on a domain they control with a low-TTL record: it resolves to a public IP at validate time and to a private one (`169.254.169.254`/`127.0.0.1`) at connect time, causing a server-side fetch of internal or cloud-metadata endpoints.

**Suggested fix.** Pin the validated IP for the connection (a custom transport/resolver that reuses the checked address), or re-validate the peer address post-connect; do not rely on a separate `getaddrinfo`.

**Verification.** Confirmed 3/3 adversarial verifiers. `assert_safe_outbound_url` does its own `getaddrinfo`/IP-check, but `httpx.Client(follow_redirects=True)` re-resolves at connect with no pinned resolver and the event hook only re-checks the URL string — a genuine TOCTOU DNS-rebind SSRF on user-supplied URLs. Medium is fair.

<a id="aut-10"></a>
### AUT-10 — Auth security events (login, failed login, reset, deletion) are never logged
🟡 **MEDIUM** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: M · WS19

**Locations:** `backend/app/services/auth.py:74` (`AuthService.login`/`reset_password`); plus `backend/app/services/auth.py:132`, `backend/app/services/auth_account.py:70`.

**Evidence.** `auth.py` imports no logger and emits nothing on login success/failure, password reset, token-version bump, or account deletion. A grep for `logger|logging` in `services/auth.py` returns zero hits. No brute-force or reset-abuse signal exists anywhere upstream.

**Failure scenario.** Credential-stuffing or repeated failed logins produce no log or metric; operators cannot detect or alert on the attack, and there is no forensic trail of successful logins.

**Suggested fix.** Log structured auth events (login ok/fail with email hash + IP, reset requested/completed, session invalidation) and add a failed-login counter metric for alerting.

**Verification.** Confirmed 3/3 adversarial verifiers. `services/auth.py` imports no logger and emits nothing on login success/failure, reset, token-version bump, or deletion; no upstream guard/logging exists, matching the OWASP A09 gap. Medium is fair.

<a id="aut-26"></a>
### AUT-26 — forgot-password leaks account existence via timing (early return vs synchronous SMTP)
🟡 **MEDIUM** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS19

**Locations:** `backend/app/services/auth.py:113` (`AuthService.request_password_reset`); plus `backend/app/core/email.py:29`.

**Evidence.** For missing or inactive users the method returns the sent-message response immediately, skipping token generation, DB writes and the `send_password_reset_email` SMTP round-trip. `login()` runs a placeholder bcrypt to equalize its timing; `forgot-password` does no such equalization, so the response time diverges sharply for real active accounts. (Verifiers noted the response-body message is identical, so the leak is purely timing; scored medium despite the low record severity.)

**Failure scenario.** An attacker POSTs `/auth/forgot-password` for many emails; existing active accounts respond markedly slower (the SMTP round-trip) than non-existent ones, enumerating the user base despite the identical message body.

**Suggested fix.** Send the reset email out-of-band (queue/Celery) so the request path is constant-time regardless of account existence, or add a fixed delay floor.

**Verification.** Confirmed 3/3 adversarial verifiers. `request_password_reset` early-returns for missing/inactive users, skipping token gen, DB writes and the synchronous `smtplib` round-trip, while `login` equalizes with placeholder bcrypt; the SMTP delta reliably enumerates active accounts.

---

<a id="aut-11"></a>
### AUT-11 — config.py inbox_poll comment has botched edit artifact 'new_string classification'
⚪ **LOW** · 📝 doc · Status: ☐ open · Confidence: certain (3/5 verifiers) · Effort: XS · WS40

**Merge note.** Merges the exact duplicate AUT-12 (uid 232) — same artifact at the same line.

**Locations:** `backend/app/core/config.py:209` (`Settings.inbox_poll_interval_seconds`).

**Evidence.** Line 209 reads `# How often beat polls mailboxes for new_string classification (seconds).` The token `new_string` is a leftover from an Edit `old_string`/`new_string` operation; a grep for `new_string|old_string` in `backend/app` hits only this line. It should read "new message classification."

**Failure scenario.** A reader of the canonical settings source-of-truth file sees a nonsensical comment that signals an unreviewed automated edit slipped into core config; no runtime impact.

**Suggested fix.** Replace `new_string classification` with `new message classification`.

**Verification.** Confirmed 3/3 adversarial verifiers. config.py:209 literally reads `new_string classification`, a botched Edit-op artifact confirmed by grep (only hit); harmless doc drift, low is fair.

<a id="aut-13"></a>
### AUT-13 — No prod validator couples AUTH_COOKIE_SECURE/SameSite to FRONTEND_BASE_URL scheme
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: S · WS19

**Locations:** `backend/app/core/config.py:249` (`_reject_placeholder_secrets_outside_local`); plus `backend/app/core/config.py:54`.

**Evidence.** The only prod fail-fast validator checks placeholder secrets (config.py:249-255). Nothing rejects incoherent-but-bootable prod combos: `AUTH_COOKIE_SECURE=true` with an `http` `FRONTEND_BASE_URL`, or `SAMESITE=none` without Secure. WS3 established a fail-fast-on-unsafe-prod-config pattern; these siblings are unguarded.

**Failure scenario.** A non-local environment boots happily with `AUTH_COOKIE_SECURE=true` over HTTP (silent auth breakage) or `SameSite=none` without Secure (cookie rejected by browsers), instead of failing fast at startup.

**Suggested fix.** Extend the `model_validator`: when `environment != local`, reject `SAMESITE=none` unless secure, and warn/reject a Secure cookie paired with an `http://` `frontend_base_url`.

**Verification.** Confirmed 3/3 adversarial verifiers. The only `model_validator` checks placeholder secrets; nothing couples `auth_cookie_secure`/`samesite` to environment or `frontend_base_url` scheme, so incoherent prod combos boot silently. Pure misconfig/hardening, so low not medium.

<a id="aut-15"></a>
### AUT-15 — No request/correlation ID in logs; log lines cannot be tied to a request or user
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: M · WS19

**Locations:** `backend/app/core/logging.py:18` (`configure_logging`).

**Evidence.** The formatter is `asctime levelname name :: message` with no request-id/user-id/trace-id, and no middleware injects one (`main.py` adds only CORS). Notifier/scrape warnings across concurrent worker runs are unattributable.

**Failure scenario.** During an incident a failed delivery or scrape log line cannot be correlated to the originating request, search, or user across interleaved worker output, slowing triage.

**Suggested fix.** Add a request-id/trace-id contextvar populated by ASGI middleware (and a worker task-id) and include it in the log format; propagate it to adapter logs.

**Verification.** Confirmed 3/3 adversarial verifiers. The logging formatter has no request/trace/user id and no middleware injects one; observability gap confirmed, correctly low.

<a id="aut-16"></a>
### AUT-16 — Logs are unstructured plaintext, not JSON; not machine-parseable for alerting
⚪ **LOW** · ♻️ refactor · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: M · WS19

**Locations:** `backend/app/core/logging.py:19` (`configure_logging`).

**Evidence.** `logging.Formatter` uses a fixed text format with no JSON handler. Security/audit events that must live in logs are emitted as free text with no fields to filter or alert on.

**Failure scenario.** CloudWatch/Loki queries for "failed login by IP" or "admin promoted user" require brittle regex; field-based alerting rules cannot be built.

**Suggested fix.** Emit structured (JSON) logs with explicit fields (event, user_id, ip, outcome), at least for security/audit events.

**Verification.** Confirmed 3/3 adversarial verifiers. The formatter emits fixed plaintext with no JSON handler; the structured-logging gap is real and distinct enough from AUT-15, correctly low.

<a id="aut-17"></a>
### AUT-17 — GDPR/audit client IP taken from unverified, unbounded X-Forwarded-For (spoofable)
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS19

**Merge note.** Consolidates four confirmed records reporting the same defect: AUT-17 (uid 3), AUT-18 (uid 7, which adds the varchar(45)-overflow angle), AUT-19 (uid 238) and AUT-20 (uid 328).

**Locations:** `backend/app/core/request_meta.py:18` (`request_meta`); plus `backend/app/models/data_request_log.py:24`, `backend/app/api/v1/auth.py:142`, `backend/app/services/auth_account.py`.

**Evidence.** `request_meta` reads `x-forwarded-for` and takes `forwarded.split(',')[0]` — the leftmost, caller-supplied hop — with no trusted-proxy allowlist and no length cap. The committed `nginx.conf` proxies nothing, so the API sees the client header verbatim. `test_request_meta` confirms the first XFF entry wins. This IP is persisted to `DataRequestLog.ip_address`, a `String(45)`, used for GDPR export/deletion and security audit logging.

**Failure scenario.** A client sends `X-Forwarded-For: 1.2.3.4` on `/auth/me/export` or `DELETE /auth/me`; the forged IP is recorded as the audit source, poisoning the only forensic record of who requested erasure/export. Additionally, a `>45`-char XFF value overflows the `varchar(45)` column, causing a Postgres insert error and a 500 on the GDPR audit path (self-DoS).

**Suggested fix.** Only honor XFF from a configured trusted-proxy hop (parse right-to-left past trusted CIDRs), validate that it parses as an IP, and truncate/normalize before persisting; otherwise fall back to `request.client.host`.

**Verification.** Confirmed 3/3 adversarial verifiers (all four merged records confirmed 3/3). `request_meta` takes `split(',')[0]` with no trusted-proxy allowlist or length cap and persists to the GDPR `DataRequestLog`; the field is audit-only (not authz/rate-limit), so impact is audit-trail integrity plus the insert-overflow 500 — hardening, low.

<a id="aut-21"></a>
### AUT-21 — JWT decode paths do not require exp/iat (RFC 8725) — accept unexpiring tokens
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS19

**Locations:** `backend/app/core/security.py:110` (`decode_token`); plus `backend/app/core/security.py:66` (`decode_feed_token`).

**Evidence.** `jwt.decode(...)` is called without `options={'require': ['exp']}`. PyJWT only validates `exp` when it is present, so a validly-signed token minted without `exp` would be accepted indefinitely. The same omission exists in `decode_feed_token`.

**Failure scenario.** Any future or alternate issuance path (or a bug) that omits `exp` yields a non-expiring token that `decode_token`/`decode_feed_token` accept; the defense-in-depth against token-lifetime bypass is absent.

**Suggested fix.** Pass `options={'require': ['exp', 'iat', 'sub']}` (and `ver` where applicable) to both `jwt.decode` calls to fail closed on missing claims.

**Verification.** Confirmed 3/3 adversarial verifiers. Both decode paths call `jwt.decode` without `options={'require':['exp']}`; PyJWT only validates `exp` when present. App tokens always set `exp`/`iat`, so this is genuine defense-in-depth, correctly scoped low hardening.

<a id="aut-22"></a>
### AUT-22 — RSS feed JWT is a 10-year bearer credential passed in the URL
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS19

**Locations:** `backend/app/core/security.py:58` (`create_feed_token`).

**Evidence.** `create_feed_token` sets `exp = now + timedelta(days=3650)` and the token travels as a `?token=` query parameter for the feed/RSS route. Query strings routinely land in proxy/CDN/browser logs and Referer headers. The token is only revocable by bumping `feed_token_version`.

**Failure scenario.** A feed URL leaked via logs, browser history, or a Referer header grants a decade of read access to all of a user's jobs until they manually rotate.

**Suggested fix.** Shorten the feed-token lifetime and/or accept it via a header; document and encourage rotation; avoid logging query strings.

**Verification.** Confirmed 3/3 adversarial verifiers. security.py:58 sets `exp = now + 3650 days` and the feed API passes it as a `?token=` query param, revocable only via `feed_token_version` — a real long-lived-token-in-URL, low is fair.

<a id="aut-23"></a>
### AUT-23 — No security response headers (HSTS, nosniff, X-Frame-Options, Referrer-Policy) anywhere
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS20

**Merge note.** Merges the near-duplicate AUT-24 (uid 6) — same missing-headers defect.

**Locations:** `backend/app/main.py:28` (`create_app`); plus `frontend/nginx.conf:1`/`:10`.

**Evidence.** `create_app` registers only `CORSMiddleware`; no middleware adds HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options`/`frame-ancestors`, or `Referrer-Policy` (a grep for those headers/CSP in `backend/app` returns nothing). `frontend/nginx.conf` serves static assets only, does not proxy `/api`, and sets no security headers — so no edge layer adds them for the API either.

**Failure scenario.** API JSON responses (including error/redirect pages and `/docs`) ship without HSTS/nosniff/framing/referrer hardening; a missing HSTS lets an on-path attacker strip TLS on the API host, and no `X-Content-Type-Options` permits MIME sniffing on any HTML-ish response.

**Suggested fix.** Add a small response-headers middleware (HSTS in prod, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY`/`frame-ancestors`) or set them at the API reverse proxy.

**Verification.** Confirmed 3/3 adversarial verifiers (merged duplicate 3/3). `create_app` registers only `CORSMiddleware`; `nginx.conf` proxies no `/api`, so nothing adds HSTS/nosniff/framing. Defense-in-depth, low.

<a id="aut-25"></a>
### AUT-25 — Swagger /docs, /redoc and /openapi.json exposed publicly in prod
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS20

**Locations:** `backend/app/main.py:22` (`create_app`); plus `devops/terraform/modules/alb/main.tf:88`/`:121`.

**Evidence.** `FastAPI()` is created with default `docs_url`/`openapi_url` regardless of `settings.environment`, and the ALB explicitly routes `['/docs','/openapi.json','/redoc']` to the API for both the HTTP and HTTPS listeners.

**Failure scenario.** Anyone on the internet can enumerate the full API surface (every route, schema, and enum) in prod, easing targeted attacks; the docs are gated by neither auth nor environment.

**Suggested fix.** Set `docs_url`/`redoc_url`/`openapi_url` to `None` (or gate on environment) outside local/dev.

**Verification.** Confirmed 3/3 adversarial verifiers. main.py:22 uses default `docs_url`/`openapi_url` with no environment gate, and `alb/main.tf:88,121` explicitly route `/docs,/openapi.json,/redoc` to the API on both listeners; the OpenAPI surface is public in prod — low hardening is fair.

<a id="aut-27"></a>
### AUT-27 — Registration returns 409 for existing email, confirming registered addresses
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: S · WS19

**Merge note.** Merges the exact duplicate AUT-29 (uid 17) — same registration-enumeration defect.

**Locations:** `backend/app/services/auth.py:59` (`AuthService.register`).

**Evidence.** `register()` raises `ConflictError('An account with this email already exists.')` → HTTP 409 when `repo.get_by_email` is not `None`, directly disclosing whether an email is registered — in contrast to the deliberately constant messages used on login and forgot-password.

**Failure scenario.** An attacker probes `/auth/register` with candidate emails; a 409-vs-201 response cleanly enumerates registered users for phishing/credential-stuffing, undermining the anti-enumeration effort elsewhere in the same service.

**Suggested fix.** Return a neutral "check your email" response and handle the duplicate internally (send a "you already have an account" email), or accept and explicitly document the tradeoff behind rate limiting.

**Verification.** Confirmed 3/3 adversarial verifiers (merged duplicate 3/3). `register()` raises a 409 on a taken email while login/forgot-password use uniform responses, cleanly enabling email enumeration; no rate-limit or uniform-response guard on `/register`.

<a id="aut-28"></a>
### AUT-28 — Concurrent duplicate registration surfaces IntegrityError as 500 not 409
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: S · WS19

**Locations:** `backend/app/services/auth.py:59` (`AuthService.register`).

**Evidence.** `register` does a `get_by_email()` check-then-add. `User.email` has a DB unique constraint but the flush `IntegrityError` is not caught (unlike the WS5 promo-redemption path, which added savepoint + `IntegrityError` handling). Two racing registrations for the same email: one wins, the other 500s.

**Failure scenario.** Two near-simultaneous `POST /auth/register` with the same email (double-click, retry) — the loser hits the unique-constraint `IntegrityError` which bubbles to a 500, instead of the intended 409 `ConflictError`.

**Suggested fix.** Wrap the add/flush in a savepoint and translate `IntegrityError` on the email unique constraint into `ConflictError`, mirroring the promo-redemption idempotency pattern.

**Verification.** Confirmed 3/3 adversarial verifiers. `User.email` has a unique constraint and `register` does check-then-add via `repo.add()` which flushes; two concurrent same-email registrations raise an uncaught `IntegrityError` at flush → 500 instead of 409. Timing-gated and recoverable.

<a id="aut-30"></a>
### AUT-30 — reset/verify leave token row unconsumed when user inactive/missing
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: XS · WS19

**Locations:** `backend/app/services/auth.py:141` (`AuthService.reset_password`); plus `backend/app/services/auth.py:160` (`verify_email`).

**Evidence.** When the token row is found but the user is `None`/inactive, `reset_password` and `verify_email` raise without calling `delete_for_user`. `get_valid_by_hash` does not filter on user active state, so the token hash stays valid in the table until its expiry window.

**Failure scenario.** A reset link is issued while the account is active, then the account is deactivated: the token stays queryable until expiry; if the account is reactivated within the window, the still-live token can be replayed to change the password without a fresh email.

**Suggested fix.** Delete the token row (single-use consume) in the inactive/missing-user branch too, or scope `get_valid_by_hash` to also require the joined user be active.

**Verification.** Confirmed 3/3 adversarial verifiers. `get_valid_by_hash` does not filter on user active state, and `reset_password`/`verify_email` raise without `delete_for_user` when the user is `None`/inactive, leaving the token queryable until expiry; a deactivate-then-reactivate within the window allows reset-token replay. Genuine single-use lifecycle gap.

<a id="aut-31"></a>
### AUT-31 — Email-verification tokens hashed via hash_password_reset_token (naming drift)
⚪ **LOW** · 🔁 consistency · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: XS · WS19

**Locations:** `backend/app/services/auth.py:153` (`AuthService.verify_email`); plus `backend/app/services/auth.py:217` (`_issue_verification_email`), `backend/app/core/security.py:78`.

**Evidence.** `verify_email` and `_issue_verification_email` call `hash_password_reset_token()` to hash email-verification tokens. The helper is named for password reset only; reusing it for a second token family is a naming/domain-separation smell.

**Failure scenario.** Not exploitable today (the token families live in separate tables), but a refactor changing reset-token hashing (e.g. adding a reset-specific salt) would silently alter verification-token hashing too, breaking outstanding verification links.

**Suggested fix.** Rename to a neutral `hash_url_token`, or give each token family its own hash helper with a per-purpose domain-separation prefix.

**Verification.** Confirmed 3/3 adversarial verifiers. At security.py:78 and auth.py:153/217, email-verification tokens are hashed with `hash_password_reset_token()`; separate tables so no exploit today, but a real naming/domain-separation drift — low is fair.

<a id="aut-32"></a>
### AUT-32 — GDPR data export omits several user-owned entities (inbox, applications, portals)
⚪ **LOW** · 🐞 bug · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: M · WS18

**Locations:** `backend/app/services/auth_account.py:45` (`export_user_data`); plus `backend/app/repositories/application_logs.py:52`, `backend/app/repositories/inbox_classifications.py:35`, `backend/app/repositories/inbox_reply_drafts.py:21`, `backend/app/repositories/mailbox_credentials.py:13`.

**Evidence.** `UserDataExport` bundles only account/sources/searches/targets/credentials/profile/jobs. It never reads the user's `ApplicationLog`, `ApplicationArtifact`, `MailboxCredential`, `InboxClassification`, `InboxReplyDraft`/`SendLog`, or promo redemptions — all `user_id`-owned rows.

**Failure scenario.** A user exercises GDPR Art.15/20 access/portability; the export silently excludes their application history, inbox classifications, drafted/sent recruiter replies, and mailbox config — an incomplete DSAR.

**Suggested fix.** Extend `export_user_data` to include all `user_id`-scoped tables (application logs + artifacts, inbox classifications/drafts/send-logs, mailbox credential metadata, promo redemptions), each via its owner-scoped repo query.

**Verification.** Confirmed 3/3 adversarial verifiers. `export_user_data` bundles only account/sources/searches/targets/credentials/profile/jobs; `ApplicationLog` (via `seen_job.user_id`), `InboxClassification`/`ReplyDraft`/`SendLog`, `MailboxCredential` and `PromoRedemption` are user-owned and omitted — a real GDPR Art.15/20 gap, low is fair.

<a id="aut-33"></a>
### AUT-33 — Deletion destroys but never revokes mailbox OAuth tokens at providers
⚪ **LOW** · 🔒 security · Status: ☐ open · Confidence: high (3/5 verifiers) · Effort: M · WS18

**Locations:** `backend/app/services/auth_account.py:93` (`delete_user_account`).

**Evidence.** There is no revoke call anywhere (a grep for `revoke` across `services/inbox_oauth.py`, `inbox_mailbox_oauth.py` and `inbox/*oauth*.py` returns nothing). Deletion removes the encrypted `mailbox_credential` row (CASCADE) but the granted refresh-token grant stays live at the provider.

**Failure scenario.** After deletion the OAuth grant remains active at Google/Microsoft until it expires or the user manually revokes, leaving a dangling mailbox authorization the app can no longer manage.

**Suggested fix.** Call each provider's token-revocation endpoint before deleting `mailbox_credential` (best-effort, non-blocking).

**Verification.** Confirmed 3/3 adversarial verifiers. Grep confirms no provider revoke call in `auth_account`/`inbox`; `mailbox_credential` CASCADE-deletes on user delete, so the encrypted row is gone but the provider refresh-grant stays live. Real GDPR/hardening gap, low.

<a id="aut-34"></a>
### AUT-34 — GDPR data export loads every SeenJob with limit=None into memory in one request
⚪ **LOW** · ⚡ perf · Status: ☐ open · Confidence: medium (3/5 verifiers) · Effort: M · WS18

**Locations:** `backend/app/services/auth_account.py:56` (`build_user_data_export`).

**Evidence.** `jobs=[JobRead.model_validate(row) for row in jobs_repo.list_all(user_id=user_id, limit=None)]` — the export deliberately passes `limit=None`, materializing the user's entire `seen_job` history plus Pydantic models synchronously in the export request handler.

**Failure scenario.** A user with a very large job ledger triggering Export Data forces a full unbounded `SELECT` plus full in-memory serialization in one request, spiking memory and risking timeout; there is no streaming or pagination.

**Suggested fix.** Stream/paginate the export (chunked query + incremental serialization) or generate it in a background task delivered as a downloadable artifact.

**Verification.** Confirmed 3/3 adversarial verifiers. `export_user_data` passes `limit=None`, materializing the full `seen_job` history + Pydantic models in one request; a real unbounded-memory/timeout risk, though self-inflicted on the user's own data. Low is fair.
