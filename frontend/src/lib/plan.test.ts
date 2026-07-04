import { describe, expect, it } from "vitest";
import { sampleAccountPlan } from "../test/fixtures";
import {
  canAddResource,
  checkoutPlansFor,
  defaultCheckoutPlan,
  formatResourceUsage,
  planLabel,
} from "./plan";

describe("plan helpers", () => {
  it("formats resource usage", () => {
    expect(formatResourceUsage(2, 3, "sources")).toBe("2 / 3 sources used");
  });

  it("labels plans", () => {
    expect(planLabel("starter")).toBe("Starter");
    expect(planLabel("pro")).toBe("Pro");
  });

  it("lists checkout targets above the current tier", () => {
    expect(checkoutPlansFor("free")).toEqual(["starter", "plus", "pro"]);
    expect(checkoutPlansFor("starter")).toEqual(["plus", "pro"]);
    expect(checkoutPlansFor("plus")).toEqual(["pro"]);
    expect(checkoutPlansFor("pro")).toEqual([]);
  });

  it("defaults checkout to the next tier", () => {
    expect(defaultCheckoutPlan("free")).toBe("starter");
    expect(defaultCheckoutPlan("starter")).toBe("plus");
    expect(defaultCheckoutPlan("pro")).toBe("starter");
  });

  it("detects when a resource is at cap", () => {
    const atCap = {
      ...sampleAccountPlan,
      unlimited: false,
      limits: { max_searches: 3, max_sources: 3, max_targets: 1, max_auto_applies_per_day: 3 },
      usage: { searches: 3, sources: 3, targets: 1, auto_applies_last_day: 0 },
    };
    expect(canAddResource(atCap, "sources")).toBe(false);
    expect(canAddResource(sampleAccountPlan, "sources")).toBe(true);
  });
});
