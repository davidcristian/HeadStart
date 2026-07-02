import { describe, expect, it } from "vitest";
import { annualBilledTotal, formatUsd, planDisplayPrice, PLANS } from "./pricing";

describe("pricing", () => {
  it("formats zero and paid prices", () => {
    expect(formatUsd(0)).toBe("$0");
    expect(formatUsd(9.99)).toBe("$9.99");
    expect(formatUsd(10)).toBe("$10");
  });

  it("returns monthly or annual per-month price", () => {
    const pro = PLANS.find((p) => p.id === "pro")!;
    expect(planDisplayPrice(pro, "monthly")).toBe(9.99);
    expect(planDisplayPrice(pro, "annual")).toBe(8.29);
    expect(annualBilledTotal(pro)).toBe(99.48);
  });

  it("lists four tiers without Team", () => {
    expect(PLANS.map((p) => p.id)).toEqual(["free", "starter", "plus", "pro"]);
    expect(PLANS.find((p) => p.id === "pro")?.highlight).toBe(true);
  });

  it("enables self-serve checkout for all paid tiers", () => {
    expect(PLANS.filter((p) => p.checkoutEnabled).map((p) => p.id)).toEqual([
      "starter",
      "plus",
      "pro",
    ]);
  });
});
