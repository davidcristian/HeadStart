/** Settings billing card: tier-aware checkout and Stripe portal. */

import { useEffect, useState } from "react";
import { Banner, Button, Card, Field } from "../ui";
import { PromoCodeField } from "../PromoCodeField";
import { api } from "../../api";
import {
  checkoutPlansFor,
  defaultCheckoutPlan,
  paidPlanDescription,
  planLabel,
} from "../../lib/plan";
import type { PaidPlanId } from "../../lib/pricing";
import type { BillingPeriod, BillingStatus, PlanId, PromoValidation } from "../../types";

type SettingsBillingCardProps = {
  userPlan: PlanId;
};

export function SettingsBillingCard({ userPlan }: SettingsBillingCardProps) {
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [billingError, setBillingError] = useState<string>();
  const [billingBusy, setBillingBusy] = useState(false);
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>("monthly");
  const [checkoutPlan, setCheckoutPlan] = useState<PaidPlanId>(() => defaultCheckoutPlan(userPlan));
  const [appliedPromo, setAppliedPromo] = useState<PromoValidation | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadBilling() {
      try {
        const status = await api.billingStatus();
        if (!cancelled) setBilling(status);
      } catch {
        if (!cancelled) setBilling(null);
      }
    }
    void loadBilling();
    return () => {
      cancelled = true;
    };
  }, [userPlan]);

  useEffect(() => {
    setCheckoutPlan(defaultCheckoutPlan(userPlan));
  }, [userPlan]);

  const checkoutOptions = checkoutPlansFor(userPlan);

  async function startCheckout() {
    setBillingError(undefined);
    setBillingBusy(true);
    try {
      const { url } = await api.createCheckout(checkoutPlan, billingPeriod, appliedPromo?.code);
      window.location.assign(url);
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : "Could not start checkout.");
      setBillingBusy(false);
    }
  }

  async function openPortal() {
    setBillingError(undefined);
    setBillingBusy(true);
    try {
      const { url } = await api.createBillingPortal();
      window.location.assign(url);
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : "Could not open billing portal.");
      setBillingBusy(false);
    }
  }

  return (
    <Card title="Billing">
      <p>
        Current plan: <strong>{planLabel(userPlan)}</strong>
        {billing?.subscription_status ? (
          <>
            {" "}
            (subscription: <code>{billing.subscription_status}</code>)
          </>
        ) : null}
      </p>
      {billing?.configured ? (
        <>
          {billing.can_checkout && checkoutOptions.length > 0 ? (
            <>
              <p>{paidPlanDescription(checkoutPlan)}</p>
              {checkoutOptions.length > 1 ? (
                <Field label="Upgrade to">
                  <select
                    value={checkoutPlan}
                    onChange={(e) => setCheckoutPlan(e.target.value as PaidPlanId)}
                    aria-label="Checkout plan"
                  >
                    {checkoutOptions.map((plan) => (
                      <option key={plan} value={plan}>
                        {planLabel(plan)}
                      </option>
                    ))}
                  </select>
                </Field>
              ) : null}
              <Field label="Billing period">
                <select
                  value={billingPeriod}
                  onChange={(e) => setBillingPeriod(e.target.value as BillingPeriod)}
                  aria-label="Billing period"
                >
                  <option value="monthly">Monthly</option>
                  <option value="annual">Annual (save ~17%)</option>
                </select>
              </Field>
              <PromoCodeField onApplied={setAppliedPromo} disabled={billingBusy} />
              <p>
                <Button onClick={() => void startCheckout()} disabled={billingBusy}>
                  {billingBusy ? "Redirecting…" : `Upgrade to ${planLabel(checkoutPlan)}`}
                </Button>
              </p>
              {checkoutPlan === "pro" && billing.trial_days > 0 && !appliedPromo?.trial_days ? (
                <p className="muted">Includes a {billing.trial_days}-day free trial.</p>
              ) : null}
              {appliedPromo?.trial_days ? (
                <p className="muted">Promo trial: {appliedPromo.trial_days} days.</p>
              ) : null}
              <p className="muted">
                Compare all tiers on the <a href="/pricing">pricing page</a>.
              </p>
            </>
          ) : null}
          {billing.can_manage ? (
            <p>
              <Button variant="ghost" onClick={() => void openPortal()} disabled={billingBusy}>
                {billingBusy ? "Opening…" : "Manage subscription"}
              </Button>{" "}
              Change plan or cancel in the billing portal. <a href="/pricing">Compare tiers</a>
            </p>
          ) : null}
          {!billing.can_checkout && !billing.can_manage ? (
            <p>
              <a href="/pricing">View plans</a>
            </p>
          ) : null}
        </>
      ) : (
        <p>
          Paid checkout is not configured on this server. <a href="/pricing">View plans</a> or
          contact the operator to enable billing.
        </p>
      )}
      {billingError ? <Banner kind="error">{billingError}</Banner> : null}
    </Card>
  );
}
