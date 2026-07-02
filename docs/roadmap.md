# Roadmap

Living plan for JobNotifier — what to build next and why. Update this doc when
priorities shift or a milestone ships.

**Current baseline (2026-06):** core pipeline (schedule → scrape → dedupe → notify),
multi-user auth, encrypted site credentials, three scrapers (`greenhouse`,
`generic_html`, `playwright`), one notifier (`ntfy`), full CRUD UI, Docker +
Terraform AWS deploy. See [architecture.md](architecture.md) for the system
design.

---

## Phase 1 — Reliability & visibility

Goal: trust the system day-to-day before adding surface area.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Scrape health in the UI~~ | ~~Users need to know *why* a search stopped notifying~~ | **Shipped:** `last_run_at`, `last_error`, and recent `delivery_log` failures on the Searches page |
| ~~Validate-before-wait flows~~ | ~~Misconfigured selectors/URLs are painful to debug on a poll interval~~ | **Shipped:** `POST /sources/{id}/test` returns sample postings; "Run now" runs the pipeline synchronously and reports results |
| ~~Frontend test coverage~~ | ~~Backend is well tested; UI regressions are unguarded~~ | **Shipped:** Vitest smoke tests for Sources, Searches, Targets, and Jobs pages (mocked API) |
| ~~Password reset~~ | ~~Table-stakes for sharing the app with others~~ | **Shipped:** email-based reset flow with SMTP or dev log fallback; see [modules/auth.md](modules/auth.md) |

**Done when:** a user can configure a search, confirm it works, and diagnose a
failed scrape from the UI without reading worker logs.

---

## Phase 2 — Expand reach (adapters & notifiers)

Goal: cover the job boards and channels people actually use. Each addition is a
single adapter file — see [recipes.md](recipes.md).

### Scrapers (priority order)

| Adapter | Rationale | Likely strategy |
| ------- | --------- | --------------- |
| ~~Lever~~ | ~~Very common ATS in tech~~ | **Shipped:** public Postings API (`api.lever.co/v0/postings/<site>`); config `site` + optional `region: "eu"` |
| ~~Ashby~~ | ~~Fast-growing ATS~~ | **Shipped:** public Postings API (`api.ashbyhq.com/posting-api/job-board/<board>`); config `board` + optional `include_compensation` |
| ~~Workday~~ | ~~High-value but painful~~ | **Shipped:** public CXS jobs API (`POST …/wday/cxs/<tenant>/<site>/jobs`); config `tenant` + `site` + optional `region`; accepts `*.myworkdayjobs.com` board URLs |
| ~~Indeed~~ | ~~High demand aggregator search~~ | **Shipped:** parses embedded `mosaic-provider-jobcards` JSON from `/jobs` search pages; HTML card fallback; optional session cookies via [credentials](modules/credentials.md) for Cloudflare |
| ~~LinkedIn~~ | ~~High demand, high anti-bot risk~~ | **Shipped:** guest `seeMoreJobPostings/search` HTML pagination; opt-in adapter (not URL-detected); session cookies via [credentials](modules/credentials.md) when auth-walled |

### Notifiers

| Adapter | Rationale |
| ------- | --------- |
| ~~Email~~ | ~~Lowest friction for non-technical users~~ | **Shipped:** plain-text per-job emails via `SMTP_*`; target config `to` |
| ~~Slack webhook~~ | ~~Natural for dev teams~~ | **Shipped:** incoming webhook per job; target config `webhook_url` |
| ~~Discord webhook~~ | ~~Natural for dev teams~~ | **Shipped:** channel webhook per job; target config `webhook_url` |
| ~~Telegram~~ | ~~Lightweight mobile push alternative to ntfy~~ | **Shipped:** Bot API per job; target config `bot_token` + `chat_id` |

**Done when:** a typical tech job seeker can configure at least two of their
target companies without writing custom HTML selectors.

---

## Phase 3 — Smarter matching

Goal: reduce noise, increase signal.

| Item | Why |
| ---- | --- |
| ~~Richer filters~~ | ~~Keyword include/exclude, remote/hybrid/onsite, location, salary (where scraped)~~ | **Shipped:** `keywords`/`keywords_include`, `keywords_exclude`, `location`, `workplace`, `min_salary` + `salary_currency` applied post-scrape; structured filter form on Searches page |
| ~~Cross-search dedup~~ | ~~Same job URL in multiple searches should not notify twice~~ | **Shipped:** pipeline skips notification when a normalized URL was already recorded in any of the user's searches; per-search `seen_job` rows are still written for the Jobs feed |
| ~~Digest mode~~ | ~~Batch notifications ("5 new jobs this hour") to avoid alert fatigue~~ | **Shipped:** per-search `notification_mode` (`immediate`/`digest`) + `digest_interval_seconds`; jobs queue in `pending_digest` and flush on beat |
| ~~Job lifecycle~~ | ~~Mark seen / applied / archived; optional "job closed" on re-scrape~~ | **Shipped:** `seen_job.status`; `PATCH /jobs/{id}`; pipeline marks missing listings `closed`; Jobs page filters + row actions |

**Done when:** power users can run several overlapping searches without duplicate
pushes and can triage jobs inside the app.

---

## Phase 4 — Operate at scale

Goal: run comfortably for a small team or as a lightly hosted service.

| Item | Why |
| ---- | --- |
| ~~Metrics~~ | ~~Scrape latency, success rate, notification delivery rate (Prometheus / CloudWatch)~~ | **Shipped:** Prometheus counters/histograms on API `GET /metrics` and worker `:9090/metrics`; see [modules/metrics.md](modules/metrics.md) |
| ~~Per-site rate limits~~ | ~~Configurable politeness per adapter; avoid retry storms~~ | **Shipped:** `rate_limit_min_interval_seconds` in source/search config; per-adapter defaults in `app/scrapers/rate_limit.py` |
| ~~Admin panel~~ | ~~User management and global scrape stats~~ | **Shipped:** `/admin` UI + `GET/PATCH /admin/users`, `GET /admin/stats`; gated on `is_admin` |
| ~~Hosted deploy polish~~ | ~~Streamline [deploying-to-aws.md](deploying-to-aws.md); consider a one-click template~~ | **Shipped:** `make aws-first-deploy` chains bootstrap → terraform apply → deploy; optional `DOMAIN_NAME` + `ROUTE53_ZONE_ID`; secrets saved to `.aws-first-deploy-secrets.env` |
| ~~Playwright in production~~ | ~~Container sizing, browser pool, timeout/retry policy for JS-heavy sites~~ | **Shipped:** worker Docker target with Chromium; process-scoped browser pool; navigation timeout + retries; larger worker Fargate task + `jobnotifier-backend-worker` ECR image |

**Done when:** an operator can tell whether the system is healthy without SSH or
log diving.

---

## Phase 5 — Differentiation (optional)

Pursue only if core alerting is solid and adapter coverage is good.

| Item | Why |
| ---- | --- |
| ~~RSS / webhook export~~ | ~~Power users pipe jobs into their own tools~~ | **Shipped:** signed per-user RSS feed at `GET /feed/rss?token=...`; optional `search_id` / `status` filters; manage from Jobs page. **Shipped (webhook):** `webhook` notification target POSTs JSON per job (or digest batch) to a user-configured HTTPS URL with optional HMAC signing |
| ~~Browser extension~~ | ~~"Add this search URL" one-click from a job board tab~~ | **Shipped:** Chrome MV3 extension in `browser-extension/`; `POST /sources/detect`; see [modules/browser-extension.md](modules/browser-extension.md) |
| ~~AI summarization~~ | ~~Short "why this matches" blurb in notifications~~ | **Shipped:** per-job blurb generated in the pipeline and shown in every notifier + the Jobs feed/RSS. Pluggable providers (`heuristic` offline default, `openai`); best-effort so failures never block alerts. See [modules/summaries.md](modules/summaries.md) |
| ~~Mobile PWA~~ | ~~Lightweight jobs feed if ntfy alone is not enough~~ | **Shipped:** web manifest + service worker (offline shell); installable on mobile; bottom nav; job cards + pull-to-refresh on Jobs |

---

## Phase 6 — Production SaaS

Goal: turn JobNotifier from a self-hosted tool into a hosted product strangers can
sign up for, pay for, and trust. Work the sub-phases in order — each builds on
the previous.

### 6a — Public shell & trust

Foundation: strangers can visit the site and understand what it is before they
create an account.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Public vs app routing~~ | ~~Marketing and authenticated app must coexist cleanly~~ | **Shipped:** public `/` landing + auth screens; authenticated product under `/app/*` (gated, app shell); legacy top-level paths redirect to `/app/*`. See [modules/frontend.md](modules/frontend.md) |
| ~~Public marketing site~~ | ~~First impression and conversion~~ | **Shipped:** HeadStart-branded landing with hero, integrations, how-it-works, features, FAQ, product screenshots + tabbed demo (`frontend/public/marketing/`); regenerate via `./scripts/capture_marketing_screenshots.py` |
| ~~Legal pages~~ | ~~Required before public signup; builds trust~~ | **Shipped:** `/privacy` and `/terms` with footer links on the landing page; covers session cookies (no third-party analytics yet, so no consent banner) |

**Done when:** a visitor can browse the landing page, read legal pages, and reach
signup without hitting the authenticated app shell.

### 6b — Accounts & onboarding

Turn anonymous visitors into active users with a smooth first-run path.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Signup & onboarding polish~~ | ~~Paid SaaS needs a credible first-run path~~ | **Shipped (wizard):** guided `/app/onboarding` flow (source → notify → search → run); `onboarding_completed_at` on user + `POST /auth/me/complete-onboarding`; skip option. **Shipped (email verification):** verification email on register; `POST /auth/verify-email` + resend; `/verify-email` UI; server-side 403 until verified. Trial handling remains. |
| ~~GDPR / data compliance (baseline)~~ | ~~EU users and enterprise buyers expect it before collecting data at scale~~ | **Shipped:** `GET /auth/me/export` JSON data export; `DELETE /auth/me` account deletion with password confirmation; Settings UI |

**Done when:** a new user can verify their email, complete onboarding, and run
their first search — and can delete their account or export their data.

### 6c — Monetization

Introduce paid tiers once the public shell and onboarding work.

| Item | Why | Notes |
| ---- | --- | ----- |
| Pricing page | Users need to understand cost before committing | Tiered plans (e.g. free / pro / team), feature matrix, annual vs monthly toggle | **Shipped:** public `/pricing` with Free / Pro / Team cards, comparison table, billing-period toggle, and register CTAs; paid checkout deferred to billing item |
| Plan limits & enforcement | Free and paid tiers need server-side guardrails | Per-plan caps on searches, sources, notification targets; enforce in services, not UI only | **Shipped:** `user.plan` (`free`/`pro`/`team`, default `free`); caps + feature gates in `PlanLimitsService`; `402` on limit/feature violations; `/meta` returns plan snapshot; admin can set plan; UI shows usage on create forms |
| ~~Billing & payments~~ | Revenue and subscription lifecycle | Stripe (or similar): checkout, subscriptions, plan upgrades/downgrades, invoices, failed-payment handling, webhooks | **Shipped:** Stripe Checkout + Customer Portal; `POST /billing/webhook` updates `user.plan`; Pro monthly/annual with optional trial; see [modules/billing.md](modules/billing.md) |

**Done when:** a user can pick a plan, pay, hit enforceable limits on the free
tier, and upgrade without manual intervention.

### 6d — Launch polish

Final hosted-product details after billing works end-to-end.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Custom domain & branding~~ | ~~Hosted product credibility~~ | **Shipped:** Terraform sets `FRONTEND_BASE_URL` + `CORS_ORIGINS` from `domain_name`; optional `smtp_*` vars for transactional email; [launch-checklist.md](launch-checklist.md) for go-live steps |
| ~~GDPR / data compliance (full)~~ | ~~Enterprise and EU readiness~~ | **Shipped:** cookie consent banner; `/subprocessors` DPA/subprocessor page; `data_request_log` audit trail for export/deletion (`GET /admin/data-requests`) |

**Done when:** the product runs on a branded domain with transactional email from
that domain, and compliance items needed for a public launch are complete.

**Phase 6 overall done when:** a visitor can land on the site, understand the
product, pick a plan, pay, sign up, and use the app under enforceable plan limits
— with legal pages linked in the footer.

---

## Phase 7 — Auto-apply

Goal: let users submit job applications from JobNotifier instead of only opening
apply links. Builds on [site credentials](modules/credentials.md) (authenticated
sessions) and the job lifecycle (`seen_job.status`).

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~User profile & resume storage~~ | ~~Applications need structured candidate data~~ | **Shipped:** one Fernet-encrypted profile per user (contact, links, resume text, cover-letter template, per-field answers); returned to its owner for editing. See [modules/profile.md](modules/profile.md) |
| Per-site apply adapters | Each ATS/board has different apply flows | **Shipped:** pluggable adapters for **Greenhouse**, **Lever**, **Ashby**, **Workday**, **Google Careers**, **Microsoft Careers**, **Amazon Jobs**, **Apple Careers**, **Meta Careers**, **Indeed** (delegates to downstream ATS when the listing embeds an employer apply URL), and **LinkedIn** (delegates to those ATS adapters when possible; LinkedIn-hosted Easy Apply with dry-run + best-effort live submit). See [launch-checklist.md](launch-checklist.md#7-auto-apply-optional--know-the-limits) |
| ~~Resume file upload~~ | ~~Users expect PDF attachments when applying~~ | **Shipped:** encrypted resume file on application profile (`PUT /profile/resume`); attached on Greenhouse/Lever/Ashby/Workday live apply; plain `resume_text` fallback |
| Apply orchestration service | Business rules live in services, not routers | **Shipped:** `ApplyService.apply_to_job` loads profile, credentials, and source config; delegates to applier; marks `seen_job` `applied` on success. Live submits queue via Celery (`apply_to_job` task); preview stays synchronous. |
| ~~Apply from the Jobs UI~~ | ~~Users need a one-click path~~ | **Shipped:** Apply button on supported jobs; confirm dialog with editable cover letter; preview (`dry_run`) and submit; success/failure feedback on Jobs page |
| Safety & consent | Auto-apply is high-risk | Explicit opt-in per source, dry-run/preview mode, rate limits, and clear audit log of what was submitted | **Shipped:** `source.auto_apply_enabled` (default off); live apply blocked until enabled; `application_log` table + `GET /application-logs`; Sources toggle + Application profile history UI |

**Done when:** a user with a saved credential and profile can apply to a
supported job from the Jobs page, see the result, and the job is marked
`applied` — with a clear audit trail and no silent failures.

---

## Phase 8 — Free-tier ads

Goal: offset hosting costs for free users while keeping paid tiers ad-free.

| Item | Why | Notes |
| ---- | --- | ----- |
| Ads for free users | Monetize the free tier without hard paywalls | **Shipped:** `plan.show_ads` on `GET /api/v1/meta`; `FreeTierAd` in app shell (sidebar / mobile strip); built-in Pro upgrade CTA; optional `ADS_EXTERNAL_SLOT_URL` iframe gated on cookie consent; `ADS_ENABLED=false` kill switch; see [modules/frontend.md](modules/frontend.md) |

**Done when:** free-tier users see ads in the app, paid users do not, and ad
placement does not interfere with core job-alert workflows.

---

## Phase 9 — Promo codes

Goal: let users redeem discounts, extended trials, and other promotional offers
at signup or checkout. Builds on Phase 6c billing and plan enforcement.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Promo code model & admin~~ | ~~Operators need to create and retire offers~~ | **Shipped:** `promo_code` table; admin CRUD at `GET/POST/PATCH /admin/promo-codes`; types `percent_off`, `fixed_amount`, `free_trial_days`, `plan_upgrade` |
| ~~Redemption at checkout~~ | ~~Users expect to paste a code before paying~~ | **Shipped:** `POST /billing/promo/validate`; optional `promo_code` on checkout; Stripe Coupons/Promotion Codes synced on create |
| ~~Free-trial promos~~ | ~~Acquisition lever without manual plan overrides~~ | **Shipped:** `free_trial_days` overrides `trial_period_days` on checkout session |
| ~~Self-serve entry in UI~~ | ~~Codes should be discoverable in the funnel~~ | **Shipped:** promo field on `/pricing` and Settings → Billing; applied discount/trial shown after validation |
| ~~Audit & abuse prevention~~ | ~~Promos affect revenue and must be traceable~~ | **Shipped:** `promo_redemption` audit log; one-per-user enforcement; validation rate limit (10 / 15 min) |

**Done when:** an admin can create a promo code, a user can redeem it at checkout
or in billing settings, the correct discount or trial is applied to their
subscription, and invalid or exhausted codes fail with a clear message.

---

## Phase 10 — German legal compliance

Goal: meet Germany-specific legal requirements for operating a public website.

| Item | Why | Notes |
| ---- | --- | ----- |
| Placeholder Impressum | Required by German law (Impressumspflicht) for commercial websites | **Shipped:** `/impressum` with placeholder owner/contact sections (German); footer link on public shell |

**Done when:** visitors can open a linked Impressum page from the public footer
before the operator replaces placeholder text with final legal details.

---

## Phase 11 — Curated company & portal coverage

Goal: make it easy to follow the employers and job portals tech job seekers care
about most, and give paid users a single place to search across them.

| Item | Why | Notes |
| ---- | --- | ----- |
| FAANG / MAANG / MAMAA & unicorn portals | High-value employers use dedicated career sites and ATS boards that are not always obvious to configure | **Shipped:** `GET /portals` curated catalog (47 employers across Greenhouse, Lever, Ashby, Workday, Apple Careers, Google Careers, Meta Careers, Microsoft Careers, and Amazon Jobs); category/search filters; one-click **Add source** on Sources page; `portal_id` in `default_config` for duplicate detection. **Apple** uses the `apple_careers` scraper (hydration JSON embedded in search HTML on jobs.apple.com). **Google** uses the `google_careers` scraper (embedded JSON in careers search HTML). **Meta** uses the `meta_careers` scraper (Relay GraphQL search on metacareers.com). **Microsoft** uses the `microsoft_careers` scraper (Eightfold PCSX JSON API). **Amazon** uses the `amazon_jobs` scraper (public `search.json` API). |
| Paid portal search page | Paid users should discover and search all supported boards without manual source setup | **Shipped:** `/app/portals` searches curated portals in one request (`POST /portals/search`); bulk alert setup (`POST /portals/subscribe`) auto-creates sources + searches; Pro+ plan gate (`portal_search` feature) |

**Done when:** a paid user can open one page, pick from curated FAANG/MAANG/MAMAA
and unicorn company portals (plus other supported boards), run a search, and
subscribe to alerts without hand-configuring each company's career site.

---

## Phase 12 — Local LLM dev (llama.cpp)

Goal: let developers run AI match summaries locally during development without
cloud API keys or per-token cost, while deployed environments keep calling a
hosted API.

| Item | Why | Notes |
| ---- | --- | ----- |
| llama.cpp local summarizer | Faster iteration and zero API spend when developing locally | **Shipped:** `@register_summarizer("llamacpp")` calls a local `llama-server` OpenAI-compatible endpoint (default `http://localhost:8080/v1`); optional API key; `make llamacpp` helper (`LLAMACPP_MODEL_PATH` required). Deployed config unchanged — use `openai` or `heuristic` in prod. |

**Done when:** a developer can run summaries against a local llama.cpp server with
a one-line env change (or `make` target), see blurbs in notifications and the Jobs
feed, and production deploys are unchanged.

---

## Phase 13 — Multi-provider AI summaries

Goal: let operators (and eventually users) pick from several hosted LLM providers
for match blurbs, not only OpenAI — without branching on provider names in
services.

| Item | Why | Notes |
| ---- | --- | ----- |
| Additional summarizer adapters | Users and operators already standardize on different LLM vendors | **Shipped (Gemini):** `@register_summarizer("gemini")` calls the Google AI `generateContent` API; env `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL`; select with `SUMMARY_PROVIDER=gemini`. **Shipped (Anthropic):** `@register_summarizer("anthropic")` calls the Anthropic Messages API; env `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_VERSION`; select with `SUMMARY_PROVIDER=anthropic`. OpenAI-compatible gateways (OpenRouter, Azure) work via the existing `openai` provider and `OPENAI_BASE_URL`. See [modules/summaries.md](modules/summaries.md) and [recipes.md](recipes.md). |
| ~~Provider docs & env surface~~ | ~~Operators need a clear, per-provider config matrix~~ | **Shipped:** per-provider env vars documented in `.env.example` and `modules/summaries.md` |

**Done when:** an operator can switch `SUMMARY_PROVIDER` to at least one
non-OpenAI hosted provider (e.g. Gemini or Anthropic) with only env changes, blurbs still
appear in notifications and the Jobs feed, and failures remain best-effort
(non-blocking).

---

## Phase 14 — Four-tier pricing (replace Team)

Goal: drop the admin-only **Team** tier and ship a classic decoy ladder —
**Free → Starter → Plus → Pro** — with three self-serve paid checkouts. Work the
sub-phases in order; each is sized for a single agent with minimal context.

**Target ladder (names final; prices TBD — see notes in 14a):**

| Tier | ID | Role |
| ---- | -- | ---- |
| Free | `free` | Try the product; ads on |
| Starter | `starter` | Cheap entry — remove ads + digest |
| Plus | `plus` | **Trap** — serious price, missing HeadStart differentiators |
| Pro | `pro` | Obvious best value; highlighted on `/pricing` |

**Feature matrix (enforcement lands in 14b):**

| | Free | Starter | Plus | Pro |
| -- | ---- | ------- | ---- | --- |
| Searches / sources / targets | 3 / 3 / 1 | 5 / 5 / 2 | 10 / 10 / 3 | 20 / 20 / 5 |
| Ads | yes | no | no | no |
| Digest mode | — | ✓ | ✓ | ✓ |
| Indeed / LinkedIn / Playwright | — | — | ✓ | ✓ |
| Site credentials | — | — | ✓ | ✓ |
| AI summaries | — | — | — | ✓ |
| RSS + outbound webhooks | — | — | — | ✓ |
| Curated portal search | — | — | — | ✓ |

Admins keep unlimited access via `is_admin` (no separate plan slug). Existing
`team` subscribers migrate to `pro`.

### 14a — ADR & plan model (backend only)

Document the pricing strategy and replace `team` in the plan registry — **no**
Stripe or pricing-page work yet.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~ADR: four-tier decoy pricing~~ | ~~Capture decision before code churn~~ | **Shipped:** [adr/0010-four-tier-pricing.md](adr/0010-four-tier-pricing.md) |
| ~~`app/core/plans.py`~~ | ~~Single source of truth for limits/gates~~ | **Shipped:** `starter` + `plus` added; `team` removed; caps per matrix |
| ~~Admin effective plan~~ | ~~Operators stay unlimited~~ | **Shipped:** `PlanLimitsService.resolve_plan` maps `is_admin` → `pro` |
| ~~Data migration~~ | ~~No orphaned plan slug~~ | **Shipped:** Alembic `0019_migrate_team_to_pro` |
| ~~Schema/types sweep~~ | ~~Compile-time safety~~ | **Shipped:** `PlanId` in `schemas/plan.py`, `schemas/auth.py`, promo comments, tests |
| ~~Docs (partial)~~ | ~~Keep map accurate~~ | **Shipped:** Team deprecation in `billing.md` plan table |

**Done when:** `make check` passes; `team` is gone from valid plans; existing Team
users are `pro`; limits for all four tiers exist in `plans.py`.

### 14b — Tiered feature gates

Wire the feature matrix into enforcement — depends on **14a**.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Per-tier feature flags~~ | ~~Starter ≠ Plus ≠ Pro~~ | **Shipped:** `plan_features_for`: digest on Starter+; premium scrapers + credentials on Plus+; AI, RSS, webhooks, portal on Pro only |
| ~~Scraper/notifier gates~~ | ~~Match matrix~~ | **Shipped:** `scraper_allowed` unlocks premium scrapers on Plus+; `notifier_allowed` keeps webhooks Pro-only |
| ~~Error messages~~ | ~~Clear upgrade paths~~ | **Shipped:** `required_plan_phrase` — “Requires Pro” / “Requires Plus or Pro” / “Starter, Plus, or Pro” |
| ~~Tests~~ | ~~Regression safety~~ | **Shipped:** unit + API tests for digest, indeed, credentials, AI, portal boundaries |
| ~~Docs~~ | ~~Enforcement doc matches code~~ | **Shipped:** `billing.md` + `auth.md` limit tables |

**Done when:** a Starter user gets digest but not Indeed; a Plus user gets Indeed
but not AI summaries or portal search; Pro gets everything in the matrix.

### 14c — Pricing page UI

Public-facing four-card layout — depends on **14a** (plan IDs); prices can use
placeholders until **14d**.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~`frontend/src/lib/pricing.ts`~~ | ~~Mirror backend tiers~~ | **Shipped:** four plans; remove Team; Pro `highlight: true`; comparison table rows for new gates |
| ~~`/pricing` page~~ | ~~Conversion surface~~ | **Shipped:** four cards; annual/monthly toggle; remove Team mailto CTA |
| ~~Register CTAs~~ | ~~Funnel~~ | **Shipped:** Free → register; paid tiers → checkout when billing is configured |
| ~~`modules/frontend.md`~~ | ~~Doc sync~~ | **Shipped:** Pricing section |

**Done when:** `/pricing` shows Free / Starter / Plus / Pro with the correct
feature matrix; Team is gone from the UI.

### 14d — Stripe multi-plan checkout

Three paid Stripe price pairs — depends on **14a** and ideally **14c**.

| Item | Why | Notes |
| ---- | --- | ----- |
| ~~Price env vars~~ | ~~One pair per paid tier~~ | **Shipped:** `STRIPE_PRICE_STARTER_*`, `STRIPE_PRICE_PLUS_*`, keep `STRIPE_PRICE_PRO_*`; documented in `.env.example` |
| ~~`billing_prices.py`~~ | ~~Resolve price ID → plan~~ | **Shipped:** Map all six price IDs to `starter` / `plus` / `pro` |
| ~~Checkout API~~ | ~~Self-serve for all paid tiers~~ | **Shipped:** `POST /billing/checkout` accepts `plan: starter \| plus \| pro`; remove Team checkout blocks |
| ~~Webhook plan resolution~~ | ~~Subscription → `user.plan`~~ | **Shipped:** `checkout.session.completed` + subscription events set correct slug |
| ~~Billing status~~ | ~~UI hints~~ | **Shipped:** `can_checkout` for users not already on a paid plan |
| ~~Docs~~ | ~~Operator setup~~ | **Shipped:** Full `billing.md` rewrite for four tiers + Stripe Dashboard steps |

**Done when:** a user can subscribe to Starter, Plus, or Pro via Stripe Checkout
and webhooks persist the matching `user.plan`.

### 14e — Promo codes & admin polish

Depends on **14a** + **14d**.

| Item | Why | Notes |
| ---- | --- | ----- |
| Promo eligible plans | Codes target the right tier | Admin create form + validation: `starter` / `plus` / `pro` instead of `pro` / `team` |
| `plan_upgrade` promos | Still work across tiers | Stripe coupon metadata + redemption sets intended plan |
| Admin user panel | No Team in dropdown | Plan assign: free / starter / plus / pro |
| Settings billing UI | Upgrade paths | Show current tier; upgrade CTAs respect new ladder |

**Done when:** admins can assign any of the four tiers; promo codes validate
against the correct eligible plans; Settings reflects the user's tier.

**Phase 14 overall done when:** Team is fully removed; the public site and Stripe
both offer Free / Starter / Plus / Pro; enforcement matches the feature matrix;
admins retain unlimited access via `is_admin`.

---

## Suggested starting points

**Personal use (one job seeker):**

1. ~~Lever~~ + ~~Ashby~~ adapters
2. ~~Scrape health in the UI~~
3. ~~Email notifier as a fallback channel~~

**Shared with friends / a small team:**

1. ~~Password reset~~ + ~~onboarding polish (guided wizard)~~
2. ~~Slack notifier~~
3. ~~Digest mode~~

---

## How to pick up work

1. Choose an item from the current phase (finish Phase 1 before jumping to Phase 5).
2. Read the relevant module doc under [modules/](modules/) and follow
   [AGENTS.md](../AGENTS.md).
3. For new adapters, use [recipes.md](recipes.md) — one file, tests
   with fixtures, no live network in CI.
4. When an item ships, note it here (move to a **Shipped** subsection or strike
   through) and update the matching module doc.
