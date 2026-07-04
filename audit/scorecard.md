# Best-Practice Conformance Scorecard

Each dimension graded A (market-leading) → F (critical gaps) against professional best practice, grounded in the verified findings. Commit `2630231`.

| Dimension | Grade |
| --- | :---: |
| Security (authn/z, crypto, injection, SSRF) | **B+** |
| Architecture & modularity (SOLID, layering, adapter registries) | **A-** |
| API design (REST/OpenAPI, schema contracts) | **A-** |
| Data layer (SQLAlchemy 2.0, migrations, integrity) | **B+** |
| Testing (quality, not coverage — coverage is 100%) | **B+** |
| Documentation (accuracy, ADRs, drift) | **B** |
| Frontend practice (React 18, TanStack Query, PWA, a11y) | **B+** |
| Observability (logging, metrics, audit trail) | **B** |
| CI/CD & IaC (Terraform, Docker, workflows, AWS Well-Architected) | **B-** |
| Dependency hygiene & licensing (CVEs) | **C+** |
| Error handling & resilience (concurrency, idempotency) | **B-** |
| Performance (N+1, pagination, re-renders) | **B** |

---

## Security (authn/z, crypto, injection, SSRF) — **B+**

Core authn/z is professional-grade: repositories consistently scope queries with `user_id == user_id` (sources/searches/credentials), get_current_user enforces token_version + is_active, bcrypt with 72-byte truncation and constant-time verify, login uses a placeholder hash to defeat timing enumeration, reset bumps token_version, OAuth state is JWT-signed with 15-min exp (CSRF-safe), and secret_policy fails fast on dev placeholders in prod. SSRF is a standout: assert_safe_outbound_url is wired into every scraper call, an httpx request event-hook, notifiers, and playwright routes, blocking private/loopback/link-local/metadata/reserved. Held back from A- by one serious class the prior audit missed: user-uploaded LaTeX bundles are compiled by pdflatex WITHOUT -no-shell-escape and with no env= (inherits JWT_SECRET/CREDENTIALS_SECRET_KEY/DB creds), a \write18 RCE/secret-exfil path (compile.py:92). Plus no auth rate-limiting/lockout, unsalted single-SHA256 Fernet key (no KDF/rotation), DNS-rebinding TOCTOU in the SSRF guard, unauth worker /metrics, and JWT decode not requiring exp.

**Top gaps:**
- compile.py: user LaTeX template compiled without -no-shell-escape and with full inherited env (\write18 RCE + secret exfil via authenticated template upload) — uid 138/141, prior audit missed this class
- No rate limiting/lockout on login/forgot-password/reset/verify (uid 15/239) — brute-force + bcrypt DoS
- core/crypto.py Fernet key = unsalted single SHA-256, no KDF, no key-rotation path (uid 1/251)
- core/outbound_url.py SSRF guard resolves DNS then httpx re-resolves with follow_redirects=True — DNS-rebinding TOCTOU bypass (uid 4)
- core/metrics.py worker /metrics served unauthenticated on 0.0.0.0, ignores METRICS_TOKEN (uid 0/325)
- core/security.py JWT decode omits require exp; main.py adds no HSTS/nosniff/X-Frame security headers (uid 8/2/6)

**Exemplary:**
- SSRF defense-in-depth: assert_safe_outbound_url enforced at every scraper method, an httpx request event-hook, notifiers, and playwright routes; blocks private/loopback/link-local/reserved/metadata with an env-gated test-TLD bypass that still resolves in prod
- Consistent tenant isolation: every repository query carries `user_id == user_id` in the WHERE clause; get_current_user chains verified/admin deps and checks token_version
- Timing-safe auth: login verifies against a placeholder bcrypt hash for missing users; password reset bumps token_version to invalidate outstanding JWTs
- secret_policy.py fail-fast rejects dev placeholder JWT/credentials secrets outside local/test, and OAuth state is JWT-signed with a 15-minute expiry

## Architecture & modularity (SOLID, layering, adapter registries) — **A-**

Layering and modularity are exemplary at market best-practice. Eight adapter subsystems all use an identical ABC base + `@register_*` decorator + duplicate-key guard + lazy-import registry — adding a site/channel is genuinely one file. Verified clean dependency direction: repos/models never import services/api, and adapters never import services/repositories/models (grep-confirmed empty). Zero non-test source files exceed the 300-line cap. Services consistently scope by user_id; routers use DI + get_current_user and don't run queries (except a deliberate, commented db.commit() in jobs.py:111). Gaps are all low severity: apply.py:_load_job (line 280) issues a raw select().join() in a service, bypassing the repository boundary the code otherwise honors; portals.py:82-102 hardcodes per-adapter-key identity fields (adapter knowledge leaking into a service); plan_limits.py:68 no-op ternary and applications.py dead terminal branch; function-local import json. None are structural; they are polish. Not an A only because of the repo-bypass and adapter-key branching in services.

**Top gaps:**
- apply.py:280 _load_job runs a raw select().join(Search) directly in the service, bypassing the repository layer that otherwise owns all DB access
- services/portals.py:82-102 _config_keys_match hardcodes per-adapter-key identity fields, leaking adapter-specific knowledge into a service instead of a registry-provided identity hook
- api/v1/jobs.py:111 db.commit() places transaction control in a router (commented enqueue-race workaround, still a layering leak)
- plan_limits.py:68 no-op ternary `user.plan if not user.is_admin else user.plan` (uid 25/31) and applications.py derive_pipeline_stage dead terminal branch (uid 60)
- inbox OAuth-config class list re-enumerated across 4+ files instead of a shared constant (uid 89); SkillsLanguagesForm.tsx redefines updateRow instead of importing profileFormUtils (uid 1004)
- services/profiles.py:239/253 function-local import json, breaking module-level import convention (uid 81)

**Exemplary:**
- Uniform base+registry adapter contract across 8 subsystems with duplicate-registration guard and lazy import-on-resolve; add-a-file extensibility, no `if adapter=='x'` dispatch anywhere
- Strictly unidirectional layering verified by grep: repos/models never import services/api, and adapters never reach into services/repositories/models
- Disciplined file hygiene: zero non-test source files over the 300-line cap despite 68 applier adapters
- Multi-user isolation baked into the architecture: services take user_id, routes go through get_current_user, session lifecycle centralized in deps.get_db

## API design (REST/OpenAPI, schema contracts) — **A-**

Clean, layered, RESTful API: every route declares response_model + get_verified_user (mandatory user_id scoping), a single central exception->HTTP map (main.py:60-83) yields a uniform {detail} shape plus PlanLimitError->402 with code/plan/limit, and shared Literal enums act as contract. Frontend types/* mirror schemas faithfully (job.ts, billing.ts match). Gaps are all low-severity consistency/hardening, none critical. Real contract bug: PlanFeaturesRead (plan.py:22) omits portal_search that snapshot() emits and frontend declares, so OpenAPI misdescribes the payload. Systemic input-validation drift: inbox/admin list routes use bare `limit: int = 50` then re-validate in-body, raising pydantic error as HTTP 500 not 422 with no bounds in OpenAPI, unlike jobs/applications' Query(ge,le). Minor slips: async-accepted apply returns 200 not 202, DELETE /profile/resume returns 200+body vs 204 elsewhere, OAuth callback reflects raw error param, unbounded answers/config dicts.

**Top gaps:**
- uid30 PlanFeaturesRead omits portal_search — response schema/OpenAPI drifts from both plan_limits.snapshot() output and frontend PlanFeatures type (backend/app/schemas/plan.py:22)
- uid45/50/300 inbox & admin list `limit` use bare int + in-body schema re-validation → HTTP 500 (not 422) on out-of-bounds and no bounds in OpenAPI, unlike jobs/applications' Query(ge,le) (backend/app/api/v1/inbox.py:224, admin.py:47)
- uid305 POST /jobs/{id}/apply returns 200 status='queued' for an async-accepted request instead of 202 (backend/app/api/v1/jobs.py:120)
- uid302 DELETE /profile/resume and /resume-template return 200+body, breaking the 204 convention every other DELETE follows (backend/app/api/v1/profile.py:69,100)
- uid48/146 unbounded free-form dicts: ProfileData.answers has no size/value cap unlike skills; TargetBase.config has no per-type schema validation (backend/app/schemas/profile.py, target.py:12)
- uid47/85 OAuth callbacks reflect the raw provider `error` query param into the redirect Location unencoded (backend/app/api/v1/inbox.py:86,126,166)

**Exemplary:**
- Central exception handlers (main.py:60-83) give one canonical error shape ({detail}) with a structured 402 PlanLimitError carrying code/plan/limit — no ad-hoc error bodies in routers
- Uniform authz: every data route depends on get_verified_user and passes user.id into services for tenant scoping; admin routes layer get_current_admin; no router touches the DB directly
- Hand-written frontend types stay tightly synced with backend schemas (job.ts, billing.ts, meta.ts match 1:1) and share Literal-derived enums as a real contract
- Thin typed API client (client.ts) handles 204 no-body, single transparent refresh-on-401, and consistent ApiError(status,detail) extraction across JSON/blob paths

## Data layer (SQLAlchemy 2.0, migrations, integrity) — **B+**

Professionally built: consistent SQLAlchemy 2.0 typed Mapped[]/mapped_column, disciplined FK ondelete policies, unique constraints (uq_seen_job_search_external), a shared TimestampMixin, repositories holding queries only (no business logic), and an ordered migration for every schema change (36 total). But real gaps keep it below A. (1) DAT-9/high: claim_bootstrap_admin matches only bootstrap_user_id IS NULL while the FK is SET NULL, so deleting the bootstrap admin re-opens the lock, auto-promoting the next registrant. (2) DAT-257/44: application_artifact, promo_redemption, promo_validation_attempt cascade via DB FK only with no ORM relationship on User, and conftest never sets PRAGMA foreign_keys=ON, so SQLite tests can't exercise erasure — the 100% gate gives false assurance. (3) Hot scheduled queries lack indexes: ghost sweep filters seen_job.status/applied_at (only ix on search_id); recent_failures and cross-user URL dedup load all rows and trim/normalize in Python. (4) DataRequestLog retains user_email/IP indefinitely post-erasure. Mostly medium/low; no data-loss migration found.

**Top gaps:**
- DAT-9 (repositories/users.py:37): deleting bootstrap admin resets registration lock via SET NULL FK, auto-promoting next registrant to admin (high)
- DAT-257/44 (user.py:63, models/*): 3 user-owned tables cascade by DB FK only, no ORM relationship, and SQLite tests never enable foreign_keys pragma so erasure is untested
- DAT-267/34/42 (seen_job.py:36, ghost_detection.py): no index on seen_job.status/applied_at; ghost sweep + status filters full-scan the table every beat tick
- DAT-40/268/33 (jobs.py:60, deliveries.py:20): cross-user dedup normalizes all user URLs in Python; recent_failures loads all failed rows with no SQL LIMIT, trims in Python
- DAT-258/250 (data_request_log.py:22): user_email/ip/user_agent retained indefinitely after erasure with no purge/retention job (GDPR)
- DAT-36 (20260630_0031 migration): NOT NULL text cols lack server_default though model declares default='' (ORM-only), risking raw-insert/backfill failures

**Exemplary:**
- Uniform typed SQLAlchemy 2.0 declarative models with Mapped[]/mapped_column and a shared TimestampMixin + timezone-aware utcnow default
- Strict layering: repositories contain queries only; User declares delete-orphan ORM cascades for 13 owned tables enforcing multi-tenant erasure
- Every schema change is a discrete ordered Alembic migration (36), including follow-ups widening inbox uid to bigint and adding promo_redemption uniqueness
- Atomic bootstrap-admin claim via a single UPDATE...WHERE guarded by a RegistrationLock singleton (correct concurrency primitive, despite the SET NULL flaw)

## Testing (quality, not coverage — coverage is 100%) — **B+**

Large, genuinely behavior-driven suite: ~3007 backend test fns + 1762 frontend expect() calls, no assertion-free files. Strong practices dominate — 93 files exercise the real HttpClient via MockTransport (not stubbed adapters), 38 use the real TestClient, 71 real scraper fixtures, and cross-user isolation/403-404 authz is tested in ~38 files. But environment-fidelity gaps are systemic, not cosmetic: conftest.py never sets PRAGMA foreign_keys=ON and never runs alembic (create_all on SQLite), so all ondelete=CASCADE/SET NULL — including artifacts/promo tables that cascade ONLY via DB FK (no ORM relationship) — is effectively unverified, undercutting GDPR-erasure confidence (uid 39/38). Plus monkeypatching _is_sqlite=False to 'exercise' SKIP LOCKED that SQLite silently drops (uid 37), and true tautologies (FE asserts a 'submitted' status jobs.py never returns, uid 165; assertion-free webhook noop tests, uid 297; Indeed cookie assertion missing, uid 125). 100% coverage clearly did not equal 100% behavior verification.

**Top gaps:**
- conftest.py never enables SQLite PRAGMA foreign_keys=ON (uid 39) — CASCADE/SET NULL and DB-only cascades (artifacts/promo, no ORM rel) go unverified, weakening GDPR-erasure confidence
- Alembic migration chain never executed by tests; schema built via create_all, hiding Postgres-only server_default/constraint bugs (uid 38)
- Lock-branch tests monkeypatch _is_sqlite=False on SQLite, asserting nothing about actual FOR UPDATE SKIP LOCKED semantics (uid 37)
- Frontend coverage-theater: jobMutations.test mocks a 'submitted' apply status the real endpoint never returns (uid 165) — passes even if code were wrong
- Assertion-free Stripe-webhook 'unknown user is noop' tests cannot catch a regression (uid 297)
- Indeed hosted-submit test asserts the body but never that gated session cookies are sent (uid 125)

**Exemplary:**
- 93 files drive the real HttpClient through httpx.MockTransport, testing the true HTTP/parse path rather than stubbing adapters — adapters exercised against 71 real HTML/JSON fixtures
- 38 files use the real FastAPI TestClient for full request→service→repo integration, plus ~38 files covering cross-user isolation and 403/404 authz (BOLA/IDOR)
- Test files respect the 300-line cap and the suite is honestly high-assertion: no backend or frontend test file is entirely assertion-free

## Documentation (accuracy, ADRs, drift) — **B**

The docs set is professional, above market norm: a curated map (docs/README.md), 16 per-module docs, 12 ADRs, conventions/runbook/recipes, and a "docs are Definition of Done / code wins on conflict" policy. But a staleness thread keeps it out of the A band. Verified drift: api.md omits the whole inbox router (13+ routes) and summary-preferences router (grep: 0 matches); data-model.md omits real tables (token_version, AI cols, application_artifact, promo_*); frontend.md drops shipped /subprocessors and says PWA opens on /jobs while start_url is /app/jobs. Two docs carry corrupted text: auth.md:136 export sentence has a dangling `GET (` with its clause dropped, and config.py:209 still reads "new_string classification" (edit artifact). Legal accuracy weighs medium: SubprocessorsPage omits shipped Gemini/Anthropic + mailbox providers (GDPR Art.28). Individually low, but the volume shows docs lag recent inbox/AI/legal features.

**Top gaps:**
- api.md endpoint index omits the /inbox router (13+ routes) and /summary-preferences router (uid 291/298/236)
- Corrupted doc text: auth.md:136 export sentence loses endpoint+entity clause; config.py:209 'new_string' edit artifact (uid 294/226)
- data-model.md omits real tables/columns: token_version, AI cols, application_artifact, promo_*, data_request_log (uid 227/293)
- GDPR accuracy: Subprocessors & PrivacyPolicy omit Gemini/Anthropic + mailbox providers, understate AI/PII (uid 255/256/259)
- frontend.md drift: omits /subprocessors, start_url /app/jobs not /jobs (uid 235/234); launch-checklist contradicts LinkedIn upload code (uid 120)

**Exemplary:**
- Low-context doc architecture: docs/README.md is a routing table with an explicit rule that code wins on drift and doc updates are part of Definition of Done
- 12 ADRs (0001-0011 + template) capturing real decisions (ntfy, ECS, multi-user, encrypted credentials, httponly refresh cookie, pricing)
- conventions.md documents non-obvious choices with rationale, e.g. the 'synchronous by design' section explaining one execution model across API and worker
- Docs versioned alongside a resolved 77-finding audit backlog, treating docs as a maintained, auditable artifact

## Frontend practice (React 18, TanStack Query, PWA, a11y) — **B+**

Strong, professional React 18 frontend: strict TS, clean layering (api/hooks/pages/components), every source file under the 300-line cap, 100% test coverage, a centralized `queryKeys` registry so mutations invalidate correctly, a real focus trap with Escape + focus restore (useFocusTrap.ts), and genuine a11y effort (role=dialog, tablist, role=status, aria-labels across 20 files). PWA configured via VitePWA autoUpdate/workbox. But recurring gaps keep it from A-tier: the shared Banner (ui.tsx:66) — the main async-feedback primitive — has no role=alert/live region, so errors/success are never announced; no skip-to-content link (Layout.tsx); tablists lack linked tabpanels/roving tabindex; nested label in WorkExperienceSection; empty-name Field selects (JobsPage). Correctness: JobList.tsx:134 renders scraped job.url into href with no scheme allow-list (javascript: XSS); AuthContext logout/login never clear the Query cache (prior user PII persists); client.ts 401 refresh has no single-flight dedup; meta.ts portal_search flag reportedly never reaches UI.

**Top gaps:**
- Banner has no ARIA live region (ui.tsx:59) — async errors/success never announced; primary feedback primitive
- Scraped job URLs rendered into href with no scheme allow-list — javascript: XSS (JobList.tsx:134)
- Logout/login never clear React Query cache — prior user's PII survives into next session (AuthContext.tsx:31)
- No skip-to-content link (Layout.tsx:96); tablists lack tabpanel/roving tabindex (PortalCatalog.tsx:71); empty accessible name on Jobs filter selects (JobsPage.tsx:148)
- 401 refresh has no single-flight guard — concurrent requests fire parallel /auth/refresh POSTs (client.ts:55)
- portal_search feature flag never reaches UI; pro-plan portal search always gated off (types/meta.ts:20)

**Exemplary:**
- Centralized queryKeys registry (hooks/queries.ts) so mutations invalidate correct caches without pages knowing cache internals
- Real, complete useFocusTrap: focus-in, Tab/Shift+Tab cycling, Escape close, focus restore on unmount
- Token security: access token in-memory only, refresh via httpOnly cookie, transparent single-retry refresh with onUnauthorized bridge to AuthContext
- Disciplined modularity: strict TS, all source under 300-line cap, 100% branch coverage, clear api/hooks/lib/components/pages layering

## Observability (logging, metrics, audit trail) — **B**

Metrics are the strong pillar: core/metrics.py is a clean Prometheus layer (well-chosen counters/histograms, sane buckets, label discipline, metrics_enabled gating) consistently wired across pipeline, scrape, notification, digest and scheduler paths, with a genuinely good docs/modules/metrics.md. API /metrics uses hmac.compare_digest. DB audit trails exist (DataRequestLog with IP/UA, DeliveryLog, ApplicationLog) and auto-apply is logged. But logging is weak vs market best practice: unstructured plaintext (not JSON), no request/correlation ID or user-id (logging.py:19-20), so lines can't be tied to a request/user. Security/audit events are missing where they matter most — auth (login/failure/reset/deletion) and admin mutations emit nothing. The worker /metrics server ignores METRICS_TOKEN and binds 0.0.0.0 while docs claim the token protects it — a control contradicting its own docs. Audit IP trusts unvalidated XFF; /health does no DB/Redis readiness check. Solid, not exemplary.

**Top gaps:**
- Worker /metrics ignores METRICS_TOKEN and binds 0.0.0.0 — unauthenticated Prometheus exposure contradicting docs/modules/metrics.md's token claim (core/metrics.py:96-102; uid 0/325)
- No request/correlation ID or user-id in logs; log lines cannot be tied to a request or user (core/logging.py:18-20; uid 326)
- Logs are unstructured plaintext, not JSON — not machine-parseable for alerting/aggregation (core/logging.py:19; uid 327)
- Auth security events (login success/failure, password reset, token-version bump, account deletion) are never logged (services/auth.py; uid 324)
- Admin user mutations (deactivate, grant-admin, plan change) write no audit record and no log line (services/admin.py:26; uid 323)
- Audit-log client IP taken from unvalidated first X-Forwarded-For hop; /health is static with no DB/Redis readiness check (core/request_meta.py:18; uid 3/238/328)

**Exemplary:**
- core/metrics.py: cohesive Prometheus instrumentation with sensible histogram buckets, label discipline, and metrics_enabled short-circuiting, consistently recorded at every pipeline/scrape/notify/digest/scheduler edge
- docs/modules/metrics.md: operator-grade doc with per-process scrape targets, metric catalog, and ready-to-use PromQL for success/failure rates and p95 latency
- API /metrics token check uses hmac.compare_digest (constant-time) and 404s when metrics disabled (main.py:43-55)
- Purpose-built DB audit tables (DataRequestLog for GDPR export/delete with IP+UA, DeliveryLog per notification attempt) plus logged autonomous auto-apply (apply.py:83)

## CI/CD & IaC (Terraform, Docker, workflows, AWS Well-Architected) — **B-**

Structure is professional (modular Terraform, script-driven ops, Secrets Manager, encrypted RDS, non-root images), but this is the repo's weakest, largely un-audited dimension with real gaps. Headline: the PR quality gate runs — ci.yml enforces lint/type/test/coverage on push/PR — though ci.yml still omits check_loc/shell-validation/prettier and pre-commit omits those plus mypy/tsc/tests/coverage locally, and deploy.yml/terraform.yml stay dormant (deploy.yml is manual-only workflow_dispatch, both guard their AWS steps on vars.AWS_ROLE_ARN) until that variable/secrets are configured. Infra hardening gaps cluster in Redis (elasticache: num_cache_nodes=1, no transit/at-rest encryption, no AUTH token anywhere in TF — plaintext Celery broker + SPOF), security SG opening ALB->tasks on ports 0-65535, ECR image_tag_mutability=MUTABLE, ECS container defs with no healthCheck/readonlyRootFilesystem, and METRICS_TOKEN never set so /metrics is unauthenticated in prod. deploy.sh fires the migrate ECS task without awaiting it, then rolls all services regardless of outcome. No VPC flow logs, no ALB access logs/WAF, no dep-vuln scanning, mutable :latest in compose. Most are medium/low defense-in-depth, none critical, and the bones are solid — hence B-.

**Top gaps:**
- PR quality gate runs (.github/workflows/ci.yml: lint/type/test/coverage), but ci.yml omits check_loc/shell-validation/prettier and pre-commit omits those plus mypy/tsc/tests/coverage; deploy.yml/terraform.yml stay dormant (workflow_dispatch / vars.AWS_ROLE_ARN guards) until AWS vars/secrets are set
- ElastiCache Redis (modules/redis/main.tf): no in-transit/at-rest encryption, no AUTH token, single-node SPOF Celery broker
- deploy.sh migration is fire-and-forget (lines 26-40): services roll even if migrate fails; no await/pin of pushed image digest
- ECS tasks SG allows ALB ingress on all TCP 0-65535 (security/main.tf:61); ECR tags MUTABLE (ecr/main.tf:7)
- METRICS_TOKEN never set by Terraform (stack/main.tf) so /metrics is unauthenticated in prod; no VPC flow logs / ALB access logs / WAF
- No dependency CVE scanning (pip-audit/npm audit/Dependabot); compose + ntfy pinned to mutable :latest; ECS defs lack healthCheck/readonlyRootFilesystem

**Exemplary:**
- Clean modular Terraform: thin envs -> stack -> per-resource modules (network, alb, rds, redis, ecs, secrets, iam, ecr)
- Secrets via AWS Secrets Manager injected as ECS `secrets` (not plaintext); RDS storage_encrypted=true; TLS1.3 HTTPS listener; RDS/Redis reachable only from tasks SG
- ECR scan_on_push + lifecycle expiry; single backend image with api/worker/beat targets and non-root appuser (uid 10001)
- Script-driven ops (scripts/ + Makefile) so local/CI/deploy run identical commands

## Dependency hygiene & licensing (CVEs) — **C+**

Foundations are deliberate but operational hygiene is thin. The frontend ships a committed package-lock.json (654 hashed transitive deps) over a curated, well-maintained dep set (FastAPI, SQLAlchemy 2.0, pydantic 2, cryptography, pyjwt/bcrypt; Playwright isolated as opt-in extra). But two real gaps drag it down. (1) Zero dependency/CVE scanning: ci.yml runs only lint/type/test/coverage (deploy/terraform present but dormant behind workflow_dispatch/vars.AWS_ROLE_ARN guards) — no Dependabot/Renovate, no pip-audit/npm-audit/osv/Trivy; make check = lint+typecheck+test only. (2) Backend has no lockfile/hashes — only >= floors in pyproject.toml, so Docker builds are non-reproducible. Plus no license field in package.json/pyproject and no SBOM/NOTICE. Sound choices, incomplete stewardship.

**Top gaps:**
- No dependency/CVE scanning anywhere: ci.yml runs only lint/type/test/coverage, no Dependabot/Renovate, no pip-audit/npm audit/osv/Trivy in ci.yml, make check, or scripts/ — CVEs in 654 frontend + all backend deps undetected
- Backend has no lockfile or hashes: pyproject.toml pins only >= floors with no requirements.lock/constraints, so Docker builds are non-reproducible and exposed to silent upstream/supply-chain drift (frontend lockfile avoids this)
- License metadata missing: no 'license'/classifiers field in frontend/package.json or backend/pyproject.toml, so SBOM/license tooling can't detect the project license
- No SBOM (CycloneDX/SPDX) and no NOTICE/third-party attribution file for redistribution — no transitive-license inventory

**Exemplary:**
- Frontend supply chain locked: committed package-lock.json with 654 integrity-hashed transitive deps gives reproducible frontend builds
- Curated, current backend deps with no abandoned/high-risk packages; heavy Playwright correctly isolated as an opt-in [playwright] extra, dev tooling separated into [dev]

## Error handling & resilience (concurrency, idempotency) — **B-**

Solid foundations: session_scope commits/rolls back per unit of work (db.py:26); scrape wrapped so untrusted adapters never crash the worker (pipeline.py:127); apply failures persisted in a fresh transaction after rollback (tasks.py:105); pipeline errors still reschedule via finally (pipeline.py:133); claim_due advances next_run_at under FOR UPDATE SKIP LOCKED so overlapping ticks don't re-enqueue (searches.py:54); digest flush re-checks under a row lock (digest.py:58). But durability/idempotency has real gaps. External sends fire before the tick's commit, so acks_late+max_retries=0 redelivery or a commit failure re-notifies/double-submits (celery_app.py:25, tasks.py:94, pipeline.py:118). pending_replies/ghost_detection iterate queues with no lease and set status after send, so overlapping ticks double-send emails (pending_replies.py:133, ghost_detection.py:76). Apply's double-submit guard is check-then-insert with no unique constraint (apply.py:49). No task_time_limit; no retry/backoff anywhere; inbox OAuth refresh unlocked.

**Top gaps:**
- External sends happen before the enclosing session_scope commit; with acks_late + max_retries=0, redelivery or a commit failure re-notifies and double-submits live applications (tasks.py:94, pipeline.py:118, digest.py:57)
- pending_replies.process_due and ghost_detection.process_due iterate queues with no lease/row lock and update status after the external send, so overlapping ticks double-send emails (pending_replies.py:133, ghost_detection.py:76)
- Apply double-submit prevention is a non-atomic read-then-insert with no unique DB constraint or lock (apply.py:49,72)
- No retry/backoff on scrapes or notifier/apply sends; one transient network failure fails the whole run with no automatic recovery
- No task_time_limit/soft_time_limit; a hung Playwright scrape holds a worker slot indefinitely (celery_app.py:19)
- inbox_oauth token refresh has no row lock; concurrent refresh can rotate away the refresh token (inbox_oauth.py:63)

**Exemplary:**
- claim_due uses FOR UPDATE SKIP LOCKED and advances next_run_at atomically so overlapping/slow ticks never double-enqueue a search (searches.py:54-76)
- apply_to_job persists failure in a separate session_scope because the primary scope rolled back, with a comment on why (tasks.py:105-109)
- Pipeline wraps scrape/notify in try/except with a reschedule in finally so untrusted adapters never crash or wedge the worker (pipeline.py:127-135)
- session_scope is a clean commit-on-success / rollback-on-exception boundary reused across all worker tasks (db.py:26-39)

## Performance (N+1, pagination, re-renders) — **B**

Performance is professionally competent with a coherent, addressable debt backlog rather than user-facing breakage. Real gaps: seen_job.status/applied_at and application_log.dry_run are unindexed (only ix_seen_job_search_id exists), so the ghost-detection sweep (ghost_detection.py:18) and status-filtered queries full-scan; existing_normalized_urls_for_user (jobs.py:60) loads every user URL and normalizes in Python each scrape; sync_after_scrape (jobs.py:81) materializes all rows per scrape; recent_failures_for_searches (deliveries.py:26) has no SQL LIMIT, trimming in Python. Sync run_search_now (searches.py:54) and generate_resume (jobs.py:78) run scrape/LLM/pdflatex inline on a request thread. All are latency/scaling debt, not correctness bugs, and current list endpoints are bounded (Query le=500). Frontend is a genuine strength: centralized query-key registry with deliberate invalidation, correct useMemo/useCallback in JobsPage, no re-render storms. Digest flush uses FOR UPDATE SKIP LOCKED. Net: solid, not tuned; a load test would surface the index gaps quickly.

**Top gaps:**
- Missing DB indexes on seen_job.status/applied_at (+application_log.dry_run): ghost sweep and status-filtered pipeline/sync queries full-scan the table each beat tick (findings 267/34/42)
- existing_normalized_urls_for_user (jobs.py:60) loads ALL of a user's job URLs and normalizes in Python on every scrape — unbounded growth, no usable index (findings 40/268)
- Sync request-thread work: run_search_now (searches.py:54) runs full scrape+LLM pipeline and generate_resume (jobs.py:78) runs LLM+pdflatex inline, tying up a threadpool worker per request (findings 265/266)
- recent_failures_for_searches (deliveries.py:26) fetches all failed deliveries with no SQL LIMIT and trims per-search in Python (finding 33)
- Per-row flush loops: DigestService.queue + PendingDigest.add flush once per seen_job id; sync_after_scrape and digest delete-loop avoid set-based SQL (findings 270/269/35)
- GDPR export passes limit=None, materializing every SeenJob for a user in one request (finding 272)

**Exemplary:**
- Frontend React Query layer: single queryKeys registry (hooks/queries.ts) enabling precise mutation-driven cache invalidation; JobsPage uses useMemo/useCallback correctly with no re-render storms
- Digest flush uses Postgres row locks (get_for_update skip_locked) with re-check under lock, preventing double-send across overlapping beat ticks
- Hot dedup path existing_external_ids uses a keyed .in_() query (jobs.py:49) rather than load-all — the right pattern is present, just not applied everywhere
- List endpoints are bounded by Query(default=100, ge=1, le=500), avoiding unbounded result sets on the primary read paths
