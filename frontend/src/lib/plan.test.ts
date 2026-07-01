import { describe, expect, it } from "vitest";
import { sampleAccountPlan } from "../test/fixtures";
import { canAddResource, formatResourceUsage, planLabel } from "./plan";

describe("plan helpers", () => {
  it("formats resource usage", () => {
    expect(formatResourceUsage(2, 3, "sources")).toBe("2 / 3 sources used");
  });

  it("labels plans", () => {
    expect(planLabel("pro")).toBe("Pro");
  });

  it("detects when a resource is at cap", () => {
    const atCap = {
      ...sampleAccountPlan,
      unlimited: false,
      limits: { max_searches: 3, max_sources: 3, max_targets: 1 },
      usage: { searches: 3, sources: 3, targets: 1 },
    };
    expect(canAddResource(atCap, "sources")).toBe(false);
    expect(canAddResource(sampleAccountPlan, "sources")).toBe(true);
  });
});
