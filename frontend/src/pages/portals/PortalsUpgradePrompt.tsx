import { Link } from "react-router-dom";
import { Banner } from "../../components/ui";
import { planLabel } from "../../lib/plan";
import type { PlanId } from "../../types";

type PortalsUpgradePromptProps = {
  plan: PlanId;
};

export function PortalsUpgradePrompt({ plan }: PortalsUpgradePromptProps) {
  return (
    <div className="page-stack">
      <h1>Company search</h1>
      <Banner kind="info">
        Search across curated FAANG-adjacent, unicorn, and AI employer portals in one place. Upgrade
        to Pro or Team to unlock cross-portal search and one-click alerts. You are on the{" "}
        {planLabel(plan)} plan.
      </Banner>
      <p>
        <Link to="/pricing">View pricing</Link> or browse individual companies on the{" "}
        <Link to="/app/sources">Sources</Link> page.
      </p>
    </div>
  );
}
