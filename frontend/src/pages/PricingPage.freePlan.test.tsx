import { mockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent } from "../lib/cookieConsent";
import { renderPublicPage } from "../test/renderPublicPage";
import { PricingPage } from "./PricingPage";
import type { Plan } from "../lib/pricing";

vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { email: "u@example.com" } }) }));

// The real PlanCta renders a register link for the free tier, so the page's own
// "not the free plan" guard is unreachable through it. Swapping in a CTA that
// always fires exercises that guard directly.
vi.mock("../components/pricing/PricingParts", () => ({
  ComparisonCell: ({ value }: { value: string | boolean }) => <span>{String(value)}</span>,
  PlanCta: ({ plan, onCheckout }: { plan: Plan; onCheckout: () => void }) => (
    <button type="button" onClick={onCheckout}>{`checkout ${plan.id}`}</button>
  ),
}));

describe("PricingPage free plan guard", () => {
  beforeEach(() => {
    clearCookieConsent();
    mockApi.createCheckout.mockReset();
    mockApi.createCheckout.mockResolvedValue({ url: "https://checkout.test/s" });
    vi.stubGlobal("location", { assign: vi.fn() });
  });

  it("does not start checkout for the free plan", async () => {
    render(renderPublicPage(<PricingPage />));

    fireEvent.click(screen.getByRole("button", { name: "checkout free" }));
    fireEvent.click(screen.getByRole("button", { name: "checkout pro" }));

    // Only the paid click reaches the API.
    await waitFor(() => expect(mockApi.createCheckout).toHaveBeenCalledTimes(1));
    expect(mockApi.createCheckout).toHaveBeenCalledWith("pro", "monthly", undefined);
  });
});
