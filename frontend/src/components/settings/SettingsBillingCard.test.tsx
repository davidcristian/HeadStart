import { mockApi } from "../../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../../test/renderWithClient";
import { SettingsBillingCard } from "./SettingsBillingCard";
import type { BillingStatus, PlanId, PromoValidation } from "../../types";

type BillingStatusResolved = Awaited<ReturnType<typeof mockApi.billingStatus>>;
type PromoResolved = Awaited<ReturnType<typeof mockApi.validatePromoCode>>;

function billing(overrides: Partial<BillingStatus> = {}): BillingStatusResolved {
  const status: BillingStatus = {
    configured: true,
    plan: "free",
    subscription_status: null,
    has_stripe_subscription: false,
    can_checkout: true,
    can_manage: false,
    trial_days: 14,
    ...overrides,
  };
  return status as BillingStatusResolved;
}

function promo(value: PromoValidation): PromoResolved {
  return value as PromoResolved;
}

function renderCard(userPlan: PlanId = "free") {
  return renderWithClient(<SettingsBillingCard userPlan={userPlan} />);
}

const assign = vi.fn();

describe("SettingsBillingCard", () => {
  beforeEach(() => {
    mockApi.billingStatus.mockReset();
    mockApi.createCheckout.mockReset();
    mockApi.createBillingPortal.mockReset();
    mockApi.validatePromoCode.mockReset();
    mockApi.createCheckout.mockResolvedValue({ url: "https://checkout.test/s" });
    mockApi.createBillingPortal.mockResolvedValue({ url: "https://portal.test/p" });
    assign.mockReset();
    vi.stubGlobal("location", { assign });
  });

  it("shows the not-configured message when billing is unavailable", async () => {
    mockApi.billingStatus.mockResolvedValue(billing({ configured: false }));
    renderCard();
    expect(await screen.findByText(/Paid checkout is not configured/)).toBeInTheDocument();
    expect(screen.getByText("Free")).toBeInTheDocument();
  });

  it("treats a billingStatus failure as unconfigured", async () => {
    mockApi.billingStatus.mockRejectedValue(new Error("nope"));
    renderCard();
    expect(await screen.findByText(/Paid checkout is not configured/)).toBeInTheDocument();
  });

  it("renders the subscription status code when present", async () => {
    mockApi.billingStatus.mockResolvedValue(
      billing({ subscription_status: "active", can_checkout: false, can_manage: true }),
    );
    renderCard();
    await screen.findByRole("button", { name: "Manage subscription" });
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("offers a plan selector for free users and updates the CTA on change", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    renderCard("free");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Upgrade to Starter" })).toBeInTheDocument(),
    );
    // Default checkout plan (Starter) shows no pro trial note.
    expect(screen.queryByText(/Includes a 14-day free trial/)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Checkout plan"), { target: { value: "pro" } });
    expect(screen.getByRole("button", { name: "Upgrade to Pro" })).toBeInTheDocument();
    // Selecting pro (with a trial and no promo) reveals the trial note.
    expect(screen.getByText(/Includes a 14-day free trial/)).toBeInTheDocument();
  });

  it("hides the plan selector when only one upgrade is available", async () => {
    mockApi.billingStatus.mockResolvedValue(billing({ plan: "plus" }));
    renderCard("plus");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Upgrade to Pro" })).toBeInTheDocument(),
    );
    expect(screen.queryByLabelText("Checkout plan")).not.toBeInTheDocument();
  });

  it("changes the billing period", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    renderCard("free");
    await screen.findByLabelText("Billing period");
    fireEvent.change(screen.getByLabelText("Billing period"), { target: { value: "annual" } });
    expect((screen.getByLabelText("Billing period") as HTMLSelectElement).value).toBe("annual");
  });

  it("starts checkout and redirects", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    renderCard("free");
    await screen.findByRole("button", { name: "Upgrade to Starter" });
    fireEvent.click(screen.getByRole("button", { name: "Upgrade to Starter" }));
    await waitFor(() => expect(mockApi.createCheckout).toHaveBeenCalled());
    expect(assign).toHaveBeenCalledWith("https://checkout.test/s");
  });

  it("shows a checkout error when it fails", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    mockApi.createCheckout.mockRejectedValue(new Error("checkout boom"));
    renderCard("free");
    await screen.findByRole("button", { name: "Upgrade to Starter" });
    fireEvent.click(screen.getByRole("button", { name: "Upgrade to Starter" }));
    expect(await screen.findByText("checkout boom")).toBeInTheDocument();
  });

  it("shows a generic checkout error for non-Error throws", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    mockApi.createCheckout.mockRejectedValue("weird");
    renderCard("free");
    await screen.findByRole("button", { name: "Upgrade to Starter" });
    fireEvent.click(screen.getByRole("button", { name: "Upgrade to Starter" }));
    expect(await screen.findByText("Could not start checkout.")).toBeInTheDocument();
  });

  it("applies a promo trial and swaps the trial note", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    mockApi.validatePromoCode.mockResolvedValue(
      promo({
        code: "TRIAL30",
        promo_type: "free_trial_days",
        description: "30-day trial",
        trial_days: 30,
        percent_off: null,
        amount_off_cents: null,
        plan_target: null,
      }),
    );
    renderCard("free");
    await screen.findByLabelText("Promo code");
    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "trial30" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Promo trial: 30 days.")).toBeInTheDocument();
    expect(screen.queryByText(/Includes a 14-day free trial/)).not.toBeInTheDocument();
  });

  it("opens the billing portal and redirects", async () => {
    mockApi.billingStatus.mockResolvedValue(
      billing({ can_checkout: false, can_manage: true, plan: "pro" }),
    );
    renderCard("pro");
    await screen.findByRole("button", { name: "Manage subscription" });
    fireEvent.click(screen.getByRole("button", { name: "Manage subscription" }));
    await waitFor(() => expect(mockApi.createBillingPortal).toHaveBeenCalled());
    expect(assign).toHaveBeenCalledWith("https://portal.test/p");
  });

  it("shows a portal error when it fails", async () => {
    mockApi.billingStatus.mockResolvedValue(billing({ can_checkout: false, can_manage: true }));
    mockApi.createBillingPortal.mockRejectedValue(new Error("portal boom"));
    renderCard("pro");
    await screen.findByRole("button", { name: "Manage subscription" });
    fireEvent.click(screen.getByRole("button", { name: "Manage subscription" }));
    expect(await screen.findByText("portal boom")).toBeInTheDocument();
  });

  it("shows a generic portal error for non-Error throws", async () => {
    mockApi.billingStatus.mockResolvedValue(billing({ can_checkout: false, can_manage: true }));
    mockApi.createBillingPortal.mockRejectedValue("weird");
    renderCard("pro");
    await screen.findByRole("button", { name: "Manage subscription" });
    fireEvent.click(screen.getByRole("button", { name: "Manage subscription" }));
    expect(await screen.findByText("Could not open billing portal.")).toBeInTheDocument();
  });

  it("falls back to a plans link when neither checkout nor manage is available", async () => {
    mockApi.billingStatus.mockResolvedValue(
      billing({ can_checkout: false, can_manage: false, plan: "pro" }),
    );
    renderCard("pro");
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "View plans" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /Upgrade/ })).not.toBeInTheDocument();
  });

  it("hides the checkout block when there are no upgrade options even if can_checkout is true", async () => {
    mockApi.billingStatus.mockResolvedValue(
      billing({ can_checkout: true, can_manage: false, plan: "pro" }),
    );
    renderCard("pro");
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "View plans" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /Upgrade/ })).not.toBeInTheDocument();
  });

  it("passes the applied promo code to checkout", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    mockApi.validatePromoCode.mockResolvedValue(
      promo({
        code: "SAVE20",
        promo_type: "percent_off",
        description: "20% off",
        trial_days: null,
        percent_off: 20,
        amount_off_cents: null,
        plan_target: null,
      }),
    );
    renderCard("free");
    await screen.findByLabelText("Promo code");
    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "save20" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await screen.findByText(/20% off/);
    fireEvent.click(screen.getByRole("button", { name: "Upgrade to Starter" }));
    await waitFor(() =>
      expect(mockApi.createCheckout).toHaveBeenCalledWith("starter", "monthly", "SAVE20"),
    );
    expect(assign).toHaveBeenCalledWith("https://checkout.test/s");
  });

  it("hides the pro trial note when an applied promo already grants a trial", async () => {
    mockApi.billingStatus.mockResolvedValue(billing());
    mockApi.validatePromoCode.mockResolvedValue(
      promo({
        code: "TRIAL30",
        promo_type: "free_trial_days",
        description: "30-day trial",
        trial_days: 30,
        percent_off: null,
        amount_off_cents: null,
        plan_target: null,
      }),
    );
    renderCard("free");
    await screen.findByLabelText("Checkout plan");
    fireEvent.change(screen.getByLabelText("Checkout plan"), { target: { value: "pro" } });
    expect(screen.getByRole("button", { name: "Upgrade to Pro" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "trial30" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    // Promo trial note replaces the built-in pro trial note.
    expect(await screen.findByText("Promo trial: 30 days.")).toBeInTheDocument();
    expect(screen.queryByText(/Includes a 14-day free trial/)).not.toBeInTheDocument();
  });

  it("omits the trial note for the pro plan when there is no trial", async () => {
    mockApi.billingStatus.mockResolvedValue(billing({ trial_days: 0 }));
    renderCard("free");
    await screen.findByLabelText("Checkout plan");
    fireEvent.change(screen.getByLabelText("Checkout plan"), { target: { value: "pro" } });
    expect(screen.getByRole("button", { name: "Upgrade to Pro" })).toBeInTheDocument();
    expect(screen.queryByText(/free trial/)).not.toBeInTheDocument();
  });
});
