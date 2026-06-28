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
| Workday | High-value but painful | Playwright + credentials; opt-in |
| LinkedIn / Indeed | High demand, high anti-bot risk | Advanced/opt-in; lean on [credentials](modules/credentials.md) |

### Notifiers

| Adapter | Rationale |
| ------- | --------- |
| Email | Lowest friction for non-technical users | **Shipped:** plain-text per-job emails via `SMTP_*`; target config `to` |
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
| Richer filters | Keyword include/exclude, remote/hybrid/onsite, location, salary (where scraped) |
| Cross-search dedup | Same job URL in multiple searches should not notify twice |
| Digest mode | Batch notifications ("5 new jobs this hour") to avoid alert fatigue |
| Job lifecycle | Mark seen / applied / archived; optional "job closed" on re-scrape |

**Done when:** power users can run several overlapping searches without duplicate
pushes and can triage jobs inside the app.

---

## Phase 4 — Operate at scale

Goal: run comfortably for a small team or as a lightly hosted service.

| Item | Why |
| ---- | --- |
| Metrics | Scrape latency, success rate, notification delivery rate (Prometheus / CloudWatch) |
| Per-site rate limits | Configurable politeness per adapter; avoid retry storms |
| Admin panel | User management and global scrape stats (`is_admin` already exists) |
| Hosted deploy polish | Streamline [deploying-to-aws.md](deploying-to-aws.md); consider a one-click template |
| Playwright in production | Container sizing, browser pool, timeout/retry policy for JS-heavy sites |

**Done when:** an operator can tell whether the system is healthy without SSH or
log diving.

---

## Phase 5 — Differentiation (optional)

Pursue only if core alerting is solid and adapter coverage is good.

| Item | Why |
| ---- | --- |
| RSS / webhook export | Power users pipe jobs into their own tools |
| Browser extension | "Add this search URL" one-click from a job board tab |
| AI summarization | Short "why this matches" blurb in notifications |
| Mobile PWA | Lightweight jobs feed if ntfy alone is not enough |

---

## Suggested starting points

**Personal use (one job seeker):**

1. ~~Lever~~ + ~~Ashby~~ adapters
2. ~~Scrape health in the UI~~
3. ~~Email notifier as a fallback channel~~

**Shared with friends / a small team:**

1. ~~Password reset~~ + onboarding polish
2. ~~Slack notifier~~
3. Digest mode

---

## How to pick up work

1. Choose an item from the current phase (finish Phase 1 before jumping to Phase 5).
2. Read the relevant module doc under [modules/](modules/) and follow
   [AGENTS.md](../AGENTS.md).
3. For new adapters, use [recipes.md](recipes.md) — one file, tests
   with fixtures, no live network in CI.
4. When an item ships, note it here (move to a **Shipped** subsection or strike
   through) and update the matching module doc.
