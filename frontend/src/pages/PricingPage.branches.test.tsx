import { mockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent } from "../lib/cookieConsent";
import { renderPublicPage } from "../test/renderPublicPage";
import { PricingPage } from "./PricingPage";

const authState = vi.hoisted(() => ({ user: null as { email: string } | null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => authState }));

const assign = vi.fn();

function renderPricing() {
  return render(renderPublicPage(<PricingPage />));
}

describe("PricingPage checkout branches", () => {
  beforeEach(() => {
    authState.user = { email: "user@example.com" };
    clearCookieConsent();
    assign.mockReset();
    mockApi.createCheckout.mockReset();
    mockApi.validatePromoCode.mockReset();
    mockApi.createCheckout.mockResolvedValue({ url: "https://checkout.stripe.test/session" });
    mockApi.validatePromoCode.mockResolvedValue({
      code: "LAUNCH20",
      promo_type: "percent_off",
      description: "20% off",
      trial_days: null,
      percent_off: 20,
      amount_off_cents: null,
      plan_target: null,
    });
    vi.stubGlobal("location", { assign });
  });

  it("toggles back to monthly billing", () => {
    renderPricing();

    // Start on monthly, switch to annual, then back to monthly.
    fireEvent.click(screen.getByRole("button", { name: /Annual/i }));
    expect(screen.getByText("$8.29")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Monthly" }));
    expect(screen.getByText("$9.99")).toBeInTheDocument();
    expect(screen.getAllByText("Billed monthly").length).toBeGreaterThan(0);
  });

  it("starts checkout and redirects when a paid plan CTA is clicked", async () => {
    renderPricing();

    fireEvent.click(screen.getByRole("button", { name: "Start with Pro" }));

    await waitFor(() =>
      expect(mockApi.createCheckout).toHaveBeenCalledWith("pro", "monthly", undefined),
    );
    expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/session");
  });

  it("passes the selected annual billing period to checkout", async () => {
    renderPricing();

    fireEvent.click(screen.getByRole("button", { name: /Annual/i }));
    fireEvent.click(screen.getByRole("button", { name: "Start with Starter" }));

    await waitFor(() =>
      expect(mockApi.createCheckout).toHaveBeenCalledWith("starter", "annual", undefined),
    );
  });

  it("surfaces an Error message when checkout fails", async () => {
    mockApi.createCheckout.mockRejectedValue(new Error("checkout boom"));
    renderPricing();

    fireEvent.click(screen.getByRole("button", { name: "Start with Pro" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("checkout boom");
    expect(assign).not.toHaveBeenCalled();
    // The button re-enables after the failed attempt.
    expect(screen.getByRole("button", { name: "Start with Pro" })).toBeEnabled();
  });

  it("forwards an applied promo code to checkout", async () => {
    renderPricing();

    // Apply a promo via the signed-in promo field, then start checkout.
    fireEvent.change(screen.getByRole("textbox", { name: "Promo code" }), {
      target: { value: "LAUNCH20" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await screen.findByRole("status");

    fireEvent.click(screen.getByRole("button", { name: "Start with Pro" }));

    await waitFor(() =>
      expect(mockApi.createCheckout).toHaveBeenCalledWith("pro", "monthly", "LAUNCH20"),
    );
  });

  it("falls back to a generic message for non-Error checkout throws", async () => {
    mockApi.createCheckout.mockRejectedValue("weird");
    renderPricing();

    fireEvent.click(screen.getByRole("button", { name: "Start with Plus" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not start checkout.");
  });
});
