# Roadmap

Living plan for HeadStart — what shipped, what is still open, and what to build
next. Update this when priorities shift or a milestone ships. Detail for shipped
behavior lives in [modules/](modules/) and [adr/](adr/), not here.

**Baseline (2026-07):** Phases **1–37** are shipped. Curated portal catalog:
**182** employers. See [architecture.md](architecture.md) for the system design.

---

## Shipped (Phases 1–37)

| Area | What landed |
| ---- | ----------- |
| Core alerting | Scrape health UI, source test / run-now, frontend tests, password reset |
| Scrapers | Greenhouse, Lever, Ashby, Workday (`*.myworkdayjobs.com` + `*.myworkdaysite.com`), SmartRecruiters, Indeed, LinkedIn, FAANG custom boards, Shopify / Uber / Snowflake careers, iCIMS, Phenom, Rippling ATS, IBM Careers, Workable, SuccessFactors CSB, generic HTML, Playwright |
| Notifiers | Email, Slack, Discord, Telegram, outbound webhook, RSS export |
| Matching | Filters, cross-search dedup, digest mode, job lifecycle |
| Ops / SaaS | Metrics, rate limits, admin, hosted deploy polish, four-tier pricing (Free → Starter → Plus → Pro), Stripe billing, promo codes, ads on free tier, legal pages + Impressum, GDPR export/delete |
| Auto-apply | Profile + resume, apply adapters for every production scraper except `generic_html` / `playwright`, pipeline auto-apply queue, application logs |
| AI | Heuristic / OpenAI / Gemini / Anthropic / llama.cpp summaries; per-user + per-purpose model prefs; tailored LaTeX resume + cover letters |
| Portals | Curated catalog + Pro cross-portal search through batch 9 (182 employers) |
| Inbox (dev-only) | Local application agent: IMAP/SMTP, Gmail, Outlook, Yahoo, Fastmail; classify / route / draft / ghost / interview handoff behind `INBOX_AGENT_ENABLED` |

Module docs: [scrapers](modules/scrapers.md), [appliers](modules/appliers.md),
[portals](modules/portals.md), [inbox](modules/inbox.md),
[billing](modules/billing.md), [summaries](modules/summaries.md).

---

## Open / deferred

No open phase checklists remain. These are the leftover candidates and next
bets — pick one when starting new work.

### Next bets (pick one)

1. **Portal catalog batch 10** — more presets on existing adapters (same pattern
   as batches 6–9).
2. **More SuccessFactors CSB employers** — only when additional public
   `*.jobs.hr.cloud.sap` (or equivalent CSB) hosts are verified. Older RMK feeds
   stay out of scope for the current scraper.
3. **Another ATS gap** — new reusable scraper (+ apply adapter when feasible)
   when a high-value board stack is still uncovered.

### Catalog candidates still blocked or deferred

| Bucket | Employers / notes |
| ------ | ----------------- |
| No public GH / Ashby / Workable board | Mistral, Replicate, Weights & Biases, Retool, GitHub |
| Too thin for catalog | OpenSea, Consensys, Stability AI, ByteDance, Trade Republic |
| No verified public board | Zoox |
| Enterprise boards not on public GH / Ashby / SR | Revolut, Klarna, Zendesk, Intuit, PayPal, Etsy, eBay, Nike, Autodesk, Qualcomm, Broadcom, Arm |
| Extra vanity boards | Second Rippling ATS / iCIMS Jibe hosts beyond current presets — none verified yet |
| SuccessFactors beyond Gore | Guessed CSB hosts NXDOMAIN / non-200 at last probe; Adidas `jobs.adidas-group.com` is older RMK |

Re-verify before adding a preset: live smoke the public board API, document
skips, keep `portal_id` unique. Catalog helpers and the preset recipe live in
[modules/portals.md](modules/portals.md) and [recipes.md](recipes.md).

### Known non-goals / constraints

- Inbox automation stays **dev / self-hosted only**
  ([adr/0011](adr/0011-inbox-dev-only.md)).
- Live apply on captcha- or credential-gated boards (Rippling, Workable Turnstile;
  iCIMS / IBM / SuccessFactors partner APIs) remains best-effort for operators
  who can supply tokens or integration users — see [appliers](modules/appliers.md).

---

## How to pick up work

1. Choose a row from **Next bets** or a re-verified employer from the deferred
   table.
2. Read the matching module doc and follow [AGENTS.md](../AGENTS.md).
3. New adapters: [recipes.md](recipes.md) (one file, fixtures, no
   live network in CI). Catalog-only: one preset file + live smoke + update the
   count in [modules/portals.md](modules/portals.md).
4. When something ships, update **this** file (baseline / open table) and the
   module doc — do not reintroduce long per-phase history here.
