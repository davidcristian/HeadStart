# Module: Billing

**Paths:** `backend/app/services/billing.py`, `backend/app/api/v1/billing.py`,
`backend/app/core/billing_prices.py`, `frontend/src/pages/SettingsPage.tsx`,
`frontend/src/pages/PricingPage.tsx`

Stripe-powered subscriptions for the Pro plan. Billing is **optional** — when
`STRIPE_*` env vars are unset the API reports `configured: false` and checkout
buttons are hidden.

## Plans

| Plan | How it is assigned |
| ---- | ------------------ |
| Free | Default for new accounts |
| Pro  | Active/trialing Stripe subscription (monthly or annual price) |
| Team | Admin panel only (`PATCH /admin/users/{id}`) — no self-serve checkout |

Plan limits and feature gates are enforced in `PlanLimitsService`; see
[auth.md](auth.md) and `app/core/plans.py`.

## Configuration

Set all of the following to enable checkout:

| Env var | Purpose |
| ------- | ------- |
| `STRIPE_SECRET_KEY` | Stripe API secret |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `POST /billing/webhook` |
| `STRIPE_PRICE_PRO_MONTHLY` | Recurring price ID for monthly Pro |
| `STRIPE_PRICE_PRO_ANNUAL` | Recurring price ID for annual Pro |
| `STRIPE_TRIAL_DAYS` | Optional trial length (default `14`; `0` disables) |

`FRONTEND_BASE_URL` is used for Checkout success/cancel and portal return URLs.

## Endpoints (prefix `/api/v1/billing`)

| Method | Path | Auth | Purpose |
| ------ | ---- | ---- | ------- |
| GET | `/status` | user | Billing capabilities + subscription state |
| POST | `/checkout` | user | Start Stripe Checkout (`plan: pro`, `billing_period`) |
| POST | `/portal` | user | Open Stripe customer portal |
| POST | `/webhook` | Stripe signature | Subscription lifecycle events |

Webhook handler updates `user.stripe_customer_id`, `stripe_subscription_id`,
`subscription_status`, and `plan` on:

- `checkout.session.completed`
- `customer.subscription.created` / `updated`
- `customer.subscription.deleted` (downgrades to `free`)

## User fields

On `user`:

- `plan` — `free` / `pro` / `team`
- `stripe_customer_id`
- `stripe_subscription_id`
- `subscription_status` — last known Stripe status (`active`, `trialing`, `past_due`, `canceled`, …)

## UI

- **Pricing** (`/pricing`): signed-in users start Pro checkout; Team remains a mailto link.
- **Settings** (`/app/settings`): upgrade to Pro, manage subscription, success/cancel banners.

## Local development

Leave Stripe env vars empty. The Free tier and admin plan overrides still work.
Use the Stripe CLI to forward webhooks when testing checkout end-to-end:

```bash
stripe listen --forward-to localhost:8000/api/v1/billing/webhook
```
