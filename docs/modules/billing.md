# Module: Billing

**Paths:** `backend/app/services/billing.py`, `backend/app/api/v1/billing.py`,
`backend/app/core/billing_prices.py`, `frontend/src/components/settings/SettingsBillingCard.tsx`,
`frontend/src/pages/SettingsPage.tsx`, `frontend/src/pages/PricingPage.tsx`

Stripe-powered subscriptions for the four public tiers (Starter, Plus, Pro).
Billing is **optional** — when `STRIPE_*` env vars are unset the API reports
`configured: false` and checkout buttons are hidden.

## Plans

| Plan | How it is assigned |
| ---- | ------------------ |
| Free | Default for new accounts |
| Starter | Self-serve checkout or admin panel |
| Plus | Self-serve checkout or admin panel |
| Pro | Self-serve checkout or admin panel |

The legacy **Team** tier is deprecated (ADR-0010); existing `team` rows migrate
to `pro`. Plan limits and feature gates are enforced in `PlanLimitsService`; see
[auth.md](auth.md) and `app/core/plans.py` for the four-tier matrix (Free /
Starter / Plus / Pro).

## Configuration

Set all of the following to enable checkout:

| Env var | Purpose |
| ------- | ------- |
| `STRIPE_SECRET_KEY` | Stripe API secret |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `POST /billing/webhook` |
| `STRIPE_PRICE_STARTER_MONTHLY` | Recurring price ID for monthly Starter |
| `STRIPE_PRICE_STARTER_ANNUAL` | Recurring price ID for annual Starter |
| `STRIPE_PRICE_PLUS_MONTHLY` | Recurring price ID for monthly Plus |
| `STRIPE_PRICE_PLUS_ANNUAL` | Recurring price ID for annual Plus |
| `STRIPE_PRICE_PRO_MONTHLY` | Recurring price ID for monthly Pro |
| `STRIPE_PRICE_PRO_ANNUAL` | Recurring price ID for annual Pro |
| `STRIPE_TRIAL_DAYS` | Optional Pro trial length (default `14`; `0` disables) |

`FRONTEND_BASE_URL` is used for Checkout success/cancel and portal return URLs.

### Stripe Dashboard setup

1. Create three Products (Starter, Plus, Pro) — or one product with three prices
   per billing interval.
2. For each paid tier, create **monthly** and **annual** recurring Prices in USD.
3. Copy each Price ID (`price_…`) into the matching env var above.
4. Configure the Customer Portal (Settings → Billing → Customer portal) so
   subscribers can change plans or cancel.
5. Add a webhook endpoint pointing at
   `https://<your-domain>/api/v1/billing/webhook` and subscribe to:
   `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`.
6. Paste the webhook signing secret into `STRIPE_WEBHOOK_SECRET`.

Promo codes (optional) create Stripe Coupon + Promotion Code objects when billing
is enabled — see [Promo codes](#promo-codes) below.

## Endpoints (prefix `/api/v1/billing`)

| Method | Path | Auth | Purpose |
| ------ | ---- | ---- | ------- |
| GET | `/status` | user | Billing capabilities + subscription state |
| POST | `/checkout` | user | Start Stripe Checkout (`plan: starter \| plus \| pro`, `billing_period`, optional `promo_code`) |
| POST | `/promo/validate` | user | Validate a promo code for the signed-in user |
| POST | `/portal` | user | Open Stripe customer portal |
| POST | `/webhook` | Stripe signature | Subscription lifecycle events |

Checkout applies `STRIPE_TRIAL_DAYS` only for **Pro**; Starter and Plus bill from
day one unless a `free_trial_days` promo overrides the trial length.

## Promo codes

Promo codes are managed in the **Admin** panel (`/admin` → Promo codes) and
redeemed at checkout.

| Type | Effect |
| ---- | ------ |
| `percent_off` | Stripe coupon (% off subscription) |
| `fixed_amount` | Stripe coupon (USD cents off) |
| `free_trial_days` | Overrides checkout `trial_period_days` |
| `plan_upgrade` | 100% off coupon; sets subscription metadata plan |

When billing is enabled, creating a promo code also creates matching Stripe
Coupon + Promotion Code objects. Validation is rate-limited (10 attempts per
15 minutes per user). Redemptions are logged in `promo_redemption`.

Admin endpoints (prefix `/api/v1/admin`):

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/promo-codes` | List all promo codes |
| POST | `/promo-codes` | Create a promo code |
| PATCH | `/promo-codes/{id}` | Update (`active`, `max_redemptions`, `expires_at`) |
| GET | `/promo-codes/{id}/redemptions` | Redemption audit log |

Webhook handler updates `user.stripe_customer_id`, `stripe_subscription_id`,
`subscription_status`, and `plan` on:

- `checkout.session.completed`
- `customer.subscription.created` / `updated`
- `customer.subscription.deleted` (downgrades to `free`)

Plan resolution prefers the Stripe Price ID (`billing_prices.plan_for_price_id`);
subscription metadata `plan` is a fallback.

## User fields

On `user`:

- `plan` — `free` / `starter` / `plus` / `pro`
- `stripe_customer_id`
- `stripe_subscription_id`
- `subscription_status` — last known Stripe status (`active`, `trialing`, `past_due`, `canceled`, …)

## UI

- **Pricing** (`/pricing`): signed-in users start Starter, Plus, or Pro checkout
  with optional promo code; billing-period toggle applies to all paid tiers.
- **Settings** (`/app/settings`): upgrade to Pro with optional promo code, manage
  subscription, success/cancel banners. Other tiers link to `/pricing`.
- **Admin** (`/app/admin`): create and retire promo codes.

## Local development

Leave Stripe env vars empty. The Free tier and admin plan overrides still work.
Use the Stripe CLI to forward webhooks when testing checkout end-to-end:

```bash
stripe listen --forward-to localhost:8000/api/v1/billing/webhook
```
