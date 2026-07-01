/** Helpers for displaying plan caps and upgrade hints. */

import type { AccountPlan, PlanId } from "../types";

const PLAN_LABELS: Record<PlanId, string> = {
  free: "Free",
  pro: "Pro",
  team: "Team",
};

/** Human-readable plan name. */
export function planLabel(plan: PlanId): string {
  return PLAN_LABELS[plan];
}

/** Usage line such as "2 / 3 sources used". */
export function formatResourceUsage(current: number, max: number, label: string): string {
  return `${current} / ${max} ${label} used`;
}

/** Whether the user can add another resource of this kind. */
export function canAddResource(plan: AccountPlan, resource: keyof AccountPlan["usage"]): boolean {
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
