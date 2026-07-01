/** Plan definitions for the public pricing page (limits are aspirational until billing ships). */

export type BillingPeriod = "monthly" | "annual";

export type PlanId = "free" | "pro" | "team";

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
    description: "Everything you need to try HeadStart on a couple of watches.",
    monthlyPrice: 0,
    annualPricePerMonth: 0,
    cta: "Get started free",
    limits: {
      searches: "Up to 3",
      sources: "Up to 3",
      targets: "1 channel",
    },
    features: [
      { label: "Greenhouse, Lever, Ashby & generic HTML scrapers", included: true },
      { label: "Keyword, location & workplace filters", included: true },
      { label: "Immediate notifications (ntfy, email, Slack, …)", included: true },
      { label: "Jobs feed & mobile PWA", included: true },
      { label: "Digest mode & AI match summaries", included: false },
      { label: "Indeed, LinkedIn & authenticated scrapers", included: false },
      { label: "RSS feed & outbound webhooks", included: false },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    description: "For active job seekers running several overlapping searches.",
    monthlyPrice: 12,
    annualPricePerMonth: 10,
    highlight: true,
    cta: "Start with Pro",
    limits: {
      searches: "Up to 15",
      sources: "Up to 15",
      targets: "5 channels",
    },
    features: [
      { label: "Everything in Free", included: true },
      { label: "Indeed, LinkedIn & site credentials", included: true },
      { label: "Digest mode to batch alerts", included: true },
      { label: "AI “why this matches” summaries", included: true },
      { label: "RSS export & signed webhooks", included: true },
      { label: "Browser extension one-click capture", included: true },
      { label: "Priority email support", included: false },
    ],
  },
  {
    id: "team",
    name: "Team",
    description: "Higher limits and support for power users or small hiring pods.",
    monthlyPrice: 29,
    annualPricePerMonth: 24,
    cta: "Contact for Team",
    limits: {
      searches: "Up to 50",
      sources: "Up to 50",
      targets: "20 channels",
    },
    features: [
      { label: "Everything in Pro", included: true },
      { label: "Priority email support", included: true },
      { label: "Early access to new scrapers", included: true },
      { label: "Higher scrape frequency defaults", included: true },
      { label: "Shared webhook targets for a pod", included: true },
      { label: "Multi-seat admin (coming soon)", included: false },
    ],
  },
];

export type ComparisonRow = {
  label: string;
  free: string | boolean;
  pro: string | boolean;
  team: string | boolean;
};

export const COMPARISON_ROWS: ComparisonRow[] = [
  { label: "Active searches", free: "3", pro: "15", team: "50" },
  { label: "Sources", free: "3", pro: "15", team: "50" },
  { label: "Notification channels", free: "1", pro: "5", team: "20" },
  { label: "Digest notifications", free: false, pro: true, team: true },
  { label: "AI match summaries", free: false, pro: true, team: true },
  { label: "Indeed & LinkedIn scrapers", free: false, pro: true, team: true },
  { label: "Site credentials (auth-walled boards)", free: false, pro: true, team: true },
  { label: "RSS & outbound webhooks", free: false, pro: true, team: true },
  { label: "Browser extension", free: false, pro: true, team: true },
  { label: "Priority support", free: false, pro: false, team: true },
];

export const PRICING_FAQ = [
  {
    q: "Can I change plans later?",
    a: "Yes. When billing launches you’ll be able to upgrade or downgrade from Settings. Downgrades take effect at the end of your billing period.",
  },
  {
    q: "What happens to my data if I downgrade?",
    a: "Your account stays intact. If you’re over the new plan’s limits, existing searches stay but you won’t be able to add new ones until you’re back under the cap.",
  },
  {
    q: "Is there a trial for paid plans?",
    a: "Pro will include a 14-day trial once checkout is live. Until then, the Free tier is fully usable with no credit card required.",
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

/** Format a USD price for display (whole dollars). */
export function formatUsd(amount: number): string {
  return amount === 0 ? "$0" : `$${amount}`;
}
