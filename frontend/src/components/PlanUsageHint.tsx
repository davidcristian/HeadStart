/** Plan usage summary for create forms. */

import { Link } from "react-router-dom";
import type { AccountPlan } from "../types";
import { atCapMessage, formatResourceUsage, planLabel } from "../lib/plan";

type Resource = keyof AccountPlan["usage"];

const RESOURCE_LABELS: Record<Resource, string> = {
  searches: "searches",
  sources: "sources",
  targets: "notification channels",
};

const LIMIT_KEYS: Record<Resource, keyof AccountPlan["limits"]> = {
  searches: "max_searches",
  sources: "max_sources",
  targets: "max_targets",
};

type Props = {
  plan: AccountPlan;
  resource: Resource;
};

export function PlanUsageHint({ plan, resource }: Props) {
  if (plan.unlimited) {
    return <p className="muted">Admin account — no plan limits.</p>;
  }

  const max = plan.limits[LIMIT_KEYS[resource]];
  const current = plan.usage[resource];
  const atCap = current >= max;

  return (
    <p className={atCap ? "plan-usage plan-usage-at-cap" : "plan-usage muted"}>
      {formatResourceUsage(current, max, RESOURCE_LABELS[resource])}
      {" · "}
      {planLabel(plan.plan)} plan
      {atCap ? (
        <>
          {" — "}
          {atCapMessage(plan, RESOURCE_LABELS[resource])} <Link to="/pricing">View plans</Link>
        </>
      ) : null}
    </p>
  );
}
