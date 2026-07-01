import { describe, expect, it } from "vitest";
import { formatUsd, planDisplayPrice, PLANS } from "./pricing";

describe("pricing", () => {
  it("formats zero and paid prices", () => {
    expect(formatUsd(0)).toBe("$0");
    expect(formatUsd(12)).toBe("$12");
  });

  it("returns monthly or annual per-month price", () => {
    const pro = PLANS.find((p) => p.id === "pro")!;
    expect(planDisplayPrice(pro, "monthly")).toBe(12);
    expect(planDisplayPrice(pro, "annual")).toBe(10);
  });
});
