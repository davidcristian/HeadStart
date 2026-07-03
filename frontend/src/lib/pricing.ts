/** Plan definitions for the public pricing page (enforced server-side via `user.plan`). */

export type BillingPeriod = "monthly" | "annual";

export type PlanId = "free" | "starter" | "plus" | "pro";

export type PaidPlanId = Extract<PlanId, "starter" | "plus" | "pro">;

export type PlanFeature = {
  label: string;
  included: boolean;
};

export type Plan = {
  id: PlanId;
  name: string;
  description: string;
  monthlyPrice: number;
  annualPricePerMonth: number;
  highlight?: boolean;
  /** Self-serve Stripe checkout when billing is configured on the server. */
  checkoutEnabled?: boolean;
  cta: string;
  limits: {
    searches: string;
    sources: string;
    targets: string;
  };
  features: PlanFeature[];
};

export const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    description: "Try HeadStart on a couple of watches — no credit card required.",
    monthlyPrice: 0,
    annualPricePerMonth: 0,
    cta: "Get started free",
    limits: {
      searches: "Up to 3",
      sources: "Up to 3",
      targets: "1 channel",
    },
    features: [
      { label: "Greenhouse, Lever, Ashby, Workday & more", included: true },
      { label: "Keyword, location & workplace filters", included: true },
      { label: "Immediate notifications (ntfy, email, Slack, …)", included: true },
      { label: "Jobs feed & mobile PWA", included: true },
      { label: "Ad-free experience", included: false },
      { label: "Digest mode", included: false },
      { label: "Indeed, LinkedIn & site credentials", included: false },
      { label: "AI summaries, RSS & portal search", included: false },
    ],
  },
  {
    id: "starter",
    name: "Starter",
    description: "Remove ads and batch alerts without paying for premium boards.",
    monthlyPrice: 2.99,
    annualPricePerMonth: 2.49,
    checkoutEnabled: true,
    cta: "Start with Starter",
    limits: {
      searches: "Up to 5",
      sources: "Up to 5",
      targets: "2 channels",
    },
    features: [
      { label: "Everything in Free", included: true },
      { label: "Ad-free in the app", included: true },
      { label: "Digest mode to batch alerts", included: true },
      { label: "Indeed, LinkedIn & Playwright scrapers", included: false },
      { label: "Site credentials for auth-walled boards", included: false },
      { label: "AI “why this matches” summaries", included: false },
      { label: "RSS export & curated portal search", included: false },
    ],
  },
  {
    id: "plus",
    name: "Plus",
    description: "Unlock premium job boards and credentials for serious watchers.",
    monthlyPrice: 7.99,
    annualPricePerMonth: 6.99,
    checkoutEnabled: true,
    cta: "Start with Plus",
    limits: {
      searches: "Up to 10",
      sources: "Up to 10",
      targets: "3 channels",
    },
    features: [
      { label: "Everything in Starter", included: true },
      { label: "Indeed, LinkedIn & Playwright scrapers", included: true },
      { label: "Encrypted site credentials", included: true },
      { label: "AI “why this matches” summaries", included: false },
      { label: "RSS export & signed webhooks", included: false },
      { label: "Curated company portal search", included: false },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    description: "HeadStart’s full toolkit — AI summaries, RSS, and one-click portal search.",
    monthlyPrice: 9.99,
    annualPricePerMonth: 8.29,
    highlight: true,
    checkoutEnabled: true,
    cta: "Start with Pro",
    limits: {
      searches: "Up to 20",
      sources: "Up to 20",
      targets: "5 channels",
    },
    features: [
      { label: "Everything in Plus", included: true },
      { label: "AI “why this matches” summaries", included: true },
      { label: "RSS export & signed webhooks", included: true },
      { label: "Curated FAANG/unicorn portal search", included: true },
    ],
  },
];

export type ComparisonRow = {
  label: string;
  free: string | boolean;
  starter: string | boolean;
  plus: string | boolean;
  pro: string | boolean;
};

export const COMPARISON_ROWS: ComparisonRow[] = [
  { label: "Active searches", free: "3", starter: "5", plus: "10", pro: "20" },
  { label: "Sources", free: "3", starter: "5", plus: "10", pro: "20" },
  { label: "Notification channels", free: "1", starter: "2", plus: "3", pro: "5" },
  { label: "Ad-free experience", free: false, starter: true, plus: true, pro: true },
  { label: "Digest notifications", free: false, starter: true, plus: true, pro: true },
  { label: "Indeed, LinkedIn & Playwright", free: false, starter: false, plus: true, pro: true },
  {
    label: "Site credentials (auth-walled boards)",
    free: false,
    starter: false,
    plus: true,
    pro: true,
  },
  { label: "AI match summaries", free: false, starter: false, plus: false, pro: true },
  { label: "RSS & outbound webhooks", free: false, starter: false, plus: false, pro: true },
  { label: "Curated company portal search", free: false, starter: false, plus: false, pro: true },
];

export const PRICING_FAQ = [
  {
    q: "Can I change plans later?",
    a: "Yes. Upgrade or downgrade from Settings → Manage subscription. Downgrades take effect at the end of your billing period.",
  },
  {
    q: "What happens to my data if I downgrade?",
    a: "Your account stays intact. If you’re over the new plan’s limits, existing searches stay but you won’t be able to add new ones until you’re back under the cap.",
  },
  {
    q: "Is there a trial for paid plans?",
    a: "Pro includes a 14-day free trial when billing is enabled on the server. The Free tier is fully usable with no credit card required.",
  },
  {
    q: "Do you offer refunds?",
    a: "Annual subscriptions will be refundable within 14 days of purchase. Monthly plans can be cancelled any time; access continues through the paid period.",
  },
];

/** Display price for a plan in the selected billing period. */
export function planDisplayPrice(plan: Plan, period: BillingPeriod): number {
  return period === "annual" ? plan.annualPricePerMonth : plan.monthlyPrice;
}

/** Format a USD price for display. */
export function formatUsd(amount: number): string {
  if (amount === 0) {
    return "$0";
  }
  return Number.isInteger(amount) ? `$${amount}` : `$${amount.toFixed(2)}`;
}

/** Annual total billed for a paid plan. */
export function annualBilledTotal(plan: Plan): number {
  return Math.round(plan.annualPricePerMonth * 12 * 100) / 100;
}
