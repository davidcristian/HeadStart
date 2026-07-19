import { describe, expect, it } from "vitest";
import {
  annualBilledTotal,
  BILLING_CURRENCY,
  formatPrice,
  planDisplayPrice,
  PLANS,
  PRICING_FAQ,
} from "./pricing";

describe("pricing", () => {
  it("formats prices in EUR with de-DE locale (FRO-35)", () => {
    expect(BILLING_CURRENCY).toBe("EUR");
    expect(formatPrice(0)).toBe("0,00\u00a0€");
    expect(formatPrice(9.99)).toBe("9,99\u00a0€");
    expect(formatPrice(10)).toBe("10,00\u00a0€");
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

  it("documents EUR VAT-inclusive pricing in the FAQ", () => {
    expect(PRICING_FAQ.some((item) => /VAT/i.test(item.q) && /EUR/i.test(item.a))).toBe(true);
  });
});
