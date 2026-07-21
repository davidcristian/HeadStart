# 0010. Four-tier decoy pricing

- **Status:** Accepted
- **Date:** 2026-07-02

## Context

HeadStart shipped with three tiers (`free`, `pro`, `team`). The admin-only
**Team** tier was a manual override with high caps but no self-serve checkout.
Billing supports Pro checkout only. Product strategy now calls for a
classic decoy ladder that nudges users toward **Pro** while keeping a low-friction
**Free** entry and paid steps in between.

Operators need a single backend source of truth for plan IDs, numeric caps, and
(later) feature gates before Stripe multi-plan checkout and the public pricing
page can ship.

## Decision

Replace **Team** with two new self-serve paid tiers and keep **Pro** as the
highlighted best value:

| Tier | ID | Role |
| ---- | -- | ---- |
| Free | `free` | Try the product; ads on |
| Starter | `starter` | Cheap entry that removes ads and adds digest |
| Plus | `plus` | Mid tier that misses HeadStart differentiators |
| Pro | `pro` | Obvious best value |

**Numeric caps (searches / sources / targets / pipeline auto-applies per rolling 24h):**

| Tier | Caps |
| ---- | ---- |
| Free | 3 / 3 / 1 / 3 |
| Starter | 5 / 5 / 2 / 5 |
| Plus | 10 / 10 / 3 / 10 |
| Pro | 20 / 20 / 5 / 20 |

**Feature matrix** (enforcement lands later):

| | Free | Starter | Plus | Pro |
| -- | ---- | ------- | ---- | --- |
| Ads | yes | no | no | no |
| Digest mode | ✗ | ✓ | ✓ | ✓ |
| Indeed / LinkedIn / Playwright | ✗ | ✗ | ✓ | ✓ |
| Site credentials | ✗ | ✗ | ✓ | ✓ |
| AI summaries | ✗ | ✗ | ✗ | ✓ |
| RSS + outbound webhooks | ✗ | ✗ | ✗ | ✓ |
| Curated portal search | ✗ | ✗ | ✗ | ✓ |

**Prices (TBD in Stripe):** working defaults for implementers are Starter $2.99,
Plus $7.99, Pro $9.99 monthly (annual pairs to be set in Dashboard).

**Admin handling:** `is_admin` users keep unlimited access via early returns in
`PlanLimitsService`; `resolve_plan` maps admins to `pro` for display, not a
separate slug.

**Migration:** `UPDATE users SET plan = 'pro' WHERE plan = 'team'`.

This ADR covers the plan registry and caps only. Feature gates, pricing UI,
Stripe price pairs, and promo/admin polish follow later.

## Consequences

- `team` is removed from `PlanId`, `VALID_PLANS`, and admin assignment.
- Existing Team subscribers become Pro (same premium features until the Plus vs
  Pro gates are refined).
- Frontend and Stripe still reference Team until those follow-ups land; backend
  rejects unknown plan slugs.
- Pro caps increase from 15/15/5 to 20/20/5 per the new matrix.

## Alternatives considered

- **Keep Team as a fourth paid tier.** Rejected; admin-only tier confuses the
  public ladder and duplicates Pro positioning.
- **Three tiers only (Free / Pro / Enterprise).** Rejected; decoy pricing needs a
  visible mid tier (Plus) and a low entry (Starter).
- **Grandfather Team users on a hidden slug.** Rejected; one-time migration to
  `pro` is simpler and Team had no Stripe linkage.
