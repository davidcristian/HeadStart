import { describe, expect, it } from "vitest";
import type { PlanId } from "../types";
import { sampleAccountPlan } from "../test/fixtures";
import {
  ADMIN_PLAN_OPTIONS,
  atCapMessage,
  canAddResource,
  checkoutPlansFor,
  defaultCheckoutPlan,
  paidPlanDescription,
  PLAN_ORDER,
} from "./plan";

describe("plan helper branches", () => {
  it("exposes admin plan options in tier order", () => {
    expect(ADMIN_PLAN_OPTIONS).toEqual([
      { value: "free", label: "Free" },
      { value: "starter", label: "Starter" },
      { value: "plus", label: "Plus" },
      { value: "pro", label: "Pro" },
    ]);
    expect(PLAN_ORDER).toEqual(["free", "starter", "plus", "pro"]);
  });

  it("offers all paid tiers for an unknown current plan", () => {
    expect(checkoutPlansFor("mystery" as PlanId)).toEqual(["starter", "plus", "pro"]);
    expect(defaultCheckoutPlan("mystery" as PlanId)).toBe("starter");
  });

  it("returns a description for a known paid plan", () => {
    expect(paidPlanDescription("pro").length).toBeGreaterThan(0);
  });

  it("returns an empty description for an unknown paid plan", () => {
    expect(paidPlanDescription("ghost" as "pro")).toBe("");
  });

  it("always allows adding when the plan is unlimited", () => {
    expect(canAddResource(sampleAccountPlan, "searches")).toBe(true);
    expect(canAddResource(sampleAccountPlan, "targets")).toBe(true);
  });

  it("maps each resource kind to its own limit key", () => {
    const capped = {
      ...sampleAccountPlan,
      unlimited: false,
      limits: { max_searches: 1, max_sources: 5, max_targets: 2 },
      usage: { searches: 1, sources: 0, targets: 2 },
    };
    expect(canAddResource(capped, "searches")).toBe(false);
    expect(canAddResource(capped, "sources")).toBe(true);
    expect(canAddResource(capped, "targets")).toBe(false);
  });

  it("returns no at-cap message for unlimited plans", () => {
    expect(atCapMessage(sampleAccountPlan, "sources")).toBe("");
  });

  it("returns an upgrade hint for capped plans", () => {
    const capped = { ...sampleAccountPlan, unlimited: false, plan: "free" as const };
    expect(atCapMessage(capped, "sources")).toBe(
      "Free plan limit reached for sources. Upgrade on the pricing page to add more.",
    );
  });
});
