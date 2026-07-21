/** Plan usage summary for create forms. */

import { Link } from "react-router-dom";
import type { AccountPlan } from "../types";
import { atCapMessage, formatResourceUsage, planLabel, type PlanResource } from "../lib/plan";

const RESOURCE_LABELS: Record<PlanResource, string> = {
  searches: "searches",
  sources: "sources",
  targets: "notification channels",
};

const LIMIT_KEYS: Record<PlanResource, keyof AccountPlan["limits"]> = {
  searches: "max_searches",
  sources: "max_sources",
  targets: "max_targets",
};

type Props = {
  plan: AccountPlan;
  resource: PlanResource;
};

export function PlanUsageHint({ plan, resource }: Props) {
  if (plan.unlimited) {
    return <p className="muted">Admin accounts have no plan limits.</p>;
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
          {". "}
          {atCapMessage(plan, RESOURCE_LABELS[resource])} <Link to="/pricing">View plans</Link>
        </>
      ) : null}
    </p>
  );
}
