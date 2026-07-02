/** Admin promo code management: create, list, and retire offers. */

import { useState } from "react";
import { Banner, Button, Card, EmptyState, Field } from "./ui";
import { api } from "../api";
import { ADMIN_PLAN_OPTIONS, planLabel } from "../lib/plan";
import type { PaidPlanId } from "../lib/pricing";
import type { PlanId, PromoCode, PromoType } from "../types";

const PROMO_TYPES: { value: PromoType; label: string }[] = [
  { value: "percent_off", label: "Percent off" },
  { value: "fixed_amount", label: "Fixed amount (cents)" },
  { value: "free_trial_days", label: "Free trial days" },
  { value: "plan_upgrade", label: "Plan upgrade (100% off)" },
];

const PAID_PLAN_OPTIONS = ADMIN_PLAN_OPTIONS.filter(
  (option): option is { value: PaidPlanId; label: string } => option.value !== "free",
);

function promoSummary(code: PromoCode): string {
  if (code.promo_type === "percent_off") return `${code.value_int}% off`;
  if (code.promo_type === "fixed_amount") return `$${(code.value_int / 100).toFixed(2)} off`;
  if (code.promo_type === "free_trial_days") return `${code.value_int}-day trial`;
  if (code.promo_type === "plan_upgrade") return `Upgrade to ${planLabel(code.plan_target ?? "free")}`;
  return code.promo_type;
}

function eligiblePlansSummary(code: PromoCode): string {
  if (!code.eligible_plans?.length) return "Any plan";
  return code.eligible_plans.map(planLabel).join(", ");
}

export function AdminPromoCodesCard() {
  const [codes, setCodes] = useState<PromoCode[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const [code, setCode] = useState("");
  const [promoType, setPromoType] = useState<PromoType>("percent_off");
  const [valueInt, setValueInt] = useState("20");
  const [planTarget, setPlanTarget] = useState<PaidPlanId>("pro");
  const [eligiblePlans, setEligiblePlans] = useState<PlanId[]>([]);
  const [maxRedemptions, setMaxRedemptions] = useState("");

  function toggleEligiblePlan(plan: PlanId) {
    setEligiblePlans((prev) =>
      prev.includes(plan) ? prev.filter((row) => row !== plan) : [...prev, plan],
    );
  }

  async function loadCodes() {
    setError(undefined);
    try {
      const rows = await api.listAdminPromoCodes();
      setCodes(rows);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load promo codes.");
    }
  }

  async function createCode() {
    setBusy(true);
    setError(undefined);
    try {
      const created = await api.createAdminPromoCode({
        code,
        promo_type: promoType,
        value_int: Number(valueInt),
        plan_target: promoType === "plan_upgrade" ? planTarget : null,
        eligible_plans: eligiblePlans.length > 0 ? eligiblePlans : null,
        max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
      });
      setCodes((prev) => [created, ...prev]);
      setCode("");
      setValueInt("20");
      setEligiblePlans([]);
      setMaxRedemptions("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create promo code.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(promo: PromoCode) {
    setError(undefined);
    try {
      const updated = await api.updateAdminPromoCode(promo.id, { active: !promo.active });
      setCodes((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update promo code.");
    }
  }

  if (!loaded) {
    return (
      <Card title="Promo codes">
        <p className="muted">Create discount and trial codes for checkout.</p>
        <Button onClick={() => void loadCodes()}>Load promo codes</Button>
      </Card>
    );
  }

  return (
    <Card title="Promo codes">
      {error ? <Banner kind="error">{error}</Banner> : null}

      <div className="admin-promo-form">
        <Field label="Code">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="LAUNCH30"
            aria-label="Promo code"
          />
        </Field>
        <Field label="Type">
          <select
            value={promoType}
            onChange={(e) => setPromoType(e.target.value as PromoType)}
            aria-label="Promo type"
          >
            {PROMO_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={promoType === "fixed_amount" ? "Amount (cents)" : "Value"}>
          <input
            type="number"
            min={1}
            value={valueInt}
            onChange={(e) => setValueInt(e.target.value)}
            aria-label="Promo value"
          />
        </Field>
        {promoType === "plan_upgrade" ? (
          <Field label="Target plan">
            <select
              value={planTarget}
              onChange={(e) => setPlanTarget(e.target.value as PaidPlanId)}
              aria-label="Target plan"
            >
              {PAID_PLAN_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
        ) : null}
        <Field
          label="Eligible plans (optional)"
          hint="Leave unchecked to allow any current plan. Check one or more to restrict redemption."
        >
          <div className="checkbox-row">
            {ADMIN_PLAN_OPTIONS.map((option) => (
              <label key={option.value}>
                <input
                  type="checkbox"
                  checked={eligiblePlans.includes(option.value)}
                  onChange={() => toggleEligiblePlan(option.value)}
                />
                {option.label}
              </label>
            ))}
          </div>
        </Field>
        <Field label="Max redemptions (optional)">
          <input
            type="number"
            min={1}
            value={maxRedemptions}
            onChange={(e) => setMaxRedemptions(e.target.value)}
            placeholder="Unlimited"
            aria-label="Max redemptions"
          />
        </Field>
        <p>
          <Button onClick={() => void createCode()} disabled={busy || !code.trim()}>
            {busy ? "Creating…" : "Create promo code"}
          </Button>
        </p>
      </div>

      {codes.length === 0 ? (
        <EmptyState>No promo codes yet.</EmptyState>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Offer</th>
              <th>Eligible</th>
              <th>Redemptions</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {codes.map((promo) => (
              <tr key={promo.id}>
                <td>
                  <code>{promo.code}</code>
                </td>
                <td>{promoSummary(promo)}</td>
                <td className="muted">{eligiblePlansSummary(promo)}</td>
                <td>
                  {promo.redemption_count}
                  {promo.max_redemptions ? ` / ${promo.max_redemptions}` : ""}
                </td>
                <td>{promo.active ? "Active" : "Retired"}</td>
                <td className="row-actions">
                  <Button variant="ghost" onClick={() => void toggleActive(promo)}>
                    {promo.active ? "Retire" : "Reactivate"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
