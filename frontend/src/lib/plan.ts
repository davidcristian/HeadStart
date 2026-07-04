/** Helpers for displaying plan caps and upgrade hints. */

import { PLANS, type PaidPlanId } from "./pricing";
import type { AccountPlan, PlanId } from "../types";

export const PLAN_ORDER: readonly PlanId[] = ["free", "starter", "plus", "pro"];

const PLAN_LABELS: Record<PlanId, string> = {
  free: "Free",
  starter: "Starter",
  plus: "Plus",
  pro: "Pro",
};

/** Options for admin plan assignment dropdowns. */
export const ADMIN_PLAN_OPTIONS = PLAN_ORDER.map((value) => ({
  value,
  label: PLAN_LABELS[value],
}));

/** Paid tiers a user on `current` can self-serve checkout to (higher tiers only). */
export function checkoutPlansFor(current: PlanId): PaidPlanId[] {
  const idx = PLAN_ORDER.indexOf(current);
  if (idx < 0) {
    return ["starter", "plus", "pro"];
  }
  return PLAN_ORDER.slice(idx + 1).filter((plan): plan is PaidPlanId => plan !== "free");
}

/** Default checkout target: the next tier up, or Starter for unknown plans. */
export function defaultCheckoutPlan(current: PlanId): PaidPlanId {
  return checkoutPlansFor(current)[0] ?? "starter";
}

/** Human-readable plan name. */
export function planLabel(plan: PlanId): string {
  return PLAN_LABELS[plan];
}

/** Short marketing description for a paid tier (Settings / billing CTAs). */
export function paidPlanDescription(plan: PaidPlanId): string {
  return PLANS.find((row) => row.id === plan)?.description ?? "";
}

/** Usage line such as "2 / 3 sources used". */
export function formatResourceUsage(current: number, max: number, label: string): string {
  return `${current} / ${max} ${label} used`;
}

/** Creatable resources enforced via plan caps (rolling auto-apply usage is separate). */
export type PlanResource = "searches" | "sources" | "targets";

/** Whether the user can add another resource of this kind. */
export function canAddResource(plan: AccountPlan, resource: PlanResource): boolean {
  if (plan.unlimited) return true;
  const key =
    resource === "searches"
      ? "max_searches"
      : resource === "sources"
        ? "max_sources"
        : "max_targets";
  return plan.usage[resource] < plan.limits[key];
}

/** Short upgrade hint when a cap is reached. */
export function atCapMessage(plan: AccountPlan, resource: string): string {
  if (plan.unlimited) return "";
  return `${planLabel(plan.plan)} plan limit reached for ${resource}. Upgrade on the pricing page to add more.`;
}
