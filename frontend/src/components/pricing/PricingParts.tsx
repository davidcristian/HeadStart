/** Presentational pieces for the public pricing page. */

import { Link } from "react-router-dom";
import type { Plan } from "../../lib/pricing";

export function ComparisonCell({ value }: { value: string | boolean }) {
  if (typeof value === "boolean") {
    const label = value ? "Included" : "Not included";
    return (
      <span className={value ? "pricing-check" : "pricing-dash"} aria-label={label}>
        {value ? "✓" : "✗"}
      </span>
    );
  }
  return <span>{value}</span>;
}

export function PlanCta({
  plan,
  user,
  checkingOut,
  onCheckout,
}: {
  plan: Plan;
  user: { email: string } | null;
  checkingOut: boolean;
  onCheckout: () => void;
}) {
  const buttonClass = plan.highlight ? "btn btn-primary btn-block" : "btn btn-ghost btn-block";

  if (plan.id === "free") {
    return (
      <Link to="/register" className={buttonClass}>
        {plan.cta}
      </Link>
    );
  }

  if (plan.checkoutEnabled && user) {
    return (
      <button type="button" className={buttonClass} disabled={checkingOut} onClick={onCheckout}>
        {checkingOut ? "Redirecting…" : plan.cta}
      </button>
    );
  }

  if (user) {
    return (
      <button type="button" className="btn btn-ghost btn-block" disabled>
        Coming soon
      </button>
    );
  }

  return (
    <Link to="/register" className={buttonClass}>
      {plan.cta}
    </Link>
  );
}
