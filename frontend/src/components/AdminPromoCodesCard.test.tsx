import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { Mock } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import type { PromoCode, PromoType } from "../types";
import { AdminPromoCodesCard } from "./AdminPromoCodesCard";

// The shared mock infers narrow return types (empty-array / object literals),
// so re-view the promo-code mocks through their real API signatures. This keeps
// `PromoCode` the authoritative type for the resolved values below.
const listPromoCodesMock = mockApi.listAdminPromoCodes as unknown as Mock<
  () => Promise<PromoCode[]>
>;
const createPromoCodeMock = mockApi.createAdminPromoCode as unknown as Mock<
  (data: unknown) => Promise<PromoCode>
>;
const updatePromoCodeMock = mockApi.updateAdminPromoCode as unknown as Mock<
  (id: number, data: unknown) => Promise<PromoCode>
>;

function promo(overrides: Partial<PromoCode> = {}): PromoCode {
  return {
    id: 1,
    code: "LAUNCH20",
    promo_type: "percent_off",
    value_int: 20,
    plan_target: null,
    max_redemptions: null,
    redemption_count: 0,
    expires_at: null,
    active: true,
    one_per_user: true,
    eligible_plans: null,
    stripe_coupon_id: null,
    stripe_promotion_code_id: null,
    created_at: "2026-06-28T00:00:00Z",
    ...overrides,
  };
}

describe("AdminPromoCodesCard", () => {
  beforeEach(() => {
    resetMockApi();
    mockApi.listAdminPromoCodes.mockResolvedValue([]);
  });

  it("loads and shows the empty state", async () => {
    renderWithClient(<AdminPromoCodesCard />);

    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(screen.getByText("No promo codes yet.")).toBeInTheDocument());
    expect(mockApi.listAdminPromoCodes).toHaveBeenCalled();
  });

  it("stays on the pre-load view and does not crash when loading fails", async () => {
    // A load failure keeps `loaded` false, so the form/list never render; the
    // catch still runs. The error banner only renders in the loaded view.
    mockApi.listAdminPromoCodes.mockRejectedValueOnce(new Error("boom"));
    renderWithClient(<AdminPromoCodesCard />);

    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(mockApi.listAdminPromoCodes).toHaveBeenCalled());
    // Still on the pre-load card; the form never appeared.
    expect(screen.getByRole("button", { name: "Load promo codes" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Promo code")).not.toBeInTheDocument();
  });

  it("swallows a non-Error load rejection without rendering the form", async () => {
    mockApi.listAdminPromoCodes.mockRejectedValueOnce("nope");
    renderWithClient(<AdminPromoCodesCard />);

    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(mockApi.listAdminPromoCodes).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Load promo codes" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Promo code")).not.toBeInTheDocument();
  });

  it("renders all promo summary types and eligibility labels", async () => {
    listPromoCodesMock.mockResolvedValue([
      promo({ id: 1, code: "PCT", promo_type: "percent_off", value_int: 25 }),
      promo({ id: 2, code: "FIXED", promo_type: "fixed_amount", value_int: 500 }),
      promo({ id: 3, code: "TRIAL", promo_type: "free_trial_days", value_int: 30 }),
      promo({
        id: 4,
        code: "UPGRADE",
        promo_type: "plan_upgrade",
        plan_target: "pro",
      }),
      promo({
        id: 5,
        code: "UPGRADENULL",
        promo_type: "plan_upgrade",
        plan_target: null,
      }),
      promo({
        id: 6,
        code: "ELIG",
        eligible_plans: ["free", "starter"],
        max_redemptions: 100,
        redemption_count: 7,
        active: false,
      }),
      // Unknown promo type exercises the defensive fallthrough in promoSummary.
      promo({
        id: 7,
        code: "UNKNOWN",
        promo_type: "mystery" as PromoType,
        value_int: 0,
      }),
    ]);

    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(screen.getByText("25% off")).toBeInTheDocument());
    expect(screen.getByText("$5.00 off")).toBeInTheDocument();
    expect(screen.getByText("30-day trial")).toBeInTheDocument();
    expect(screen.getByText("Upgrade to Pro")).toBeInTheDocument();
    expect(screen.getByText("Upgrade to Free")).toBeInTheDocument();
    expect(screen.getByText("Free, Starter")).toBeInTheDocument();
    expect(screen.getByText("7 / 100")).toBeInTheDocument();
    expect(screen.getByText("Retired")).toBeInTheDocument();
    expect(screen.getAllByText("Any plan").length).toBeGreaterThan(0);
    // Fallthrough renders the raw promo type string.
    expect(screen.getByText("mystery")).toBeInTheDocument();
  });

  it("creates a percent-off promo code and prepends it to the list", async () => {
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));
    await waitFor(() => expect(screen.getByText("No promo codes yet.")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "launch30" } });
    // Value uppercases the code input.
    expect(screen.getByLabelText("Promo code")).toHaveValue("LAUNCH30");

    // Toggle two eligible plans (check then uncheck one to exercise both branches).
    const freeCheckbox = screen.getByLabelText("Free");
    const starterCheckbox = screen.getByLabelText("Starter");
    fireEvent.click(freeCheckbox);
    fireEvent.click(starterCheckbox);
    fireEvent.click(starterCheckbox);
    expect(freeCheckbox).toBeChecked();
    expect(starterCheckbox).not.toBeChecked();

    fireEvent.change(screen.getByLabelText("Max redemptions"), { target: { value: "50" } });

    createPromoCodeMock.mockResolvedValueOnce(
      promo({ id: 42, code: "LAUNCH30", value_int: 20, eligible_plans: ["free"] }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create promo code" }));

    await waitFor(() =>
      expect(mockApi.createAdminPromoCode).toHaveBeenCalledWith({
        code: "LAUNCH30",
        promo_type: "percent_off",
        value_int: 20,
        plan_target: null,
        eligible_plans: ["free"],
        max_redemptions: 50,
      }),
    );
    await waitFor(() => expect(screen.getByText("LAUNCH30")).toBeInTheDocument());
    // Form resets after create.
    expect(screen.getByLabelText("Promo code")).toHaveValue("");
    expect(screen.getByLabelText("Max redemptions")).toHaveValue(null);
  });

  it("creates a plan-upgrade promo with a target plan and no max redemptions", async () => {
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));
    await waitFor(() => expect(screen.getByText("No promo codes yet.")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "GIFT" } });
    fireEvent.change(screen.getByLabelText("Promo type"), {
      target: { value: "plan_upgrade" },
    });
    // The target-plan select only appears for plan_upgrade.
    fireEvent.change(screen.getByLabelText("Target plan"), { target: { value: "plus" } });

    createPromoCodeMock.mockResolvedValueOnce(
      promo({ id: 7, code: "GIFT", promo_type: "plan_upgrade", plan_target: "plus" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create promo code" }));

    await waitFor(() =>
      expect(mockApi.createAdminPromoCode).toHaveBeenCalledWith(
        expect.objectContaining({
          code: "GIFT",
          promo_type: "plan_upgrade",
          plan_target: "plus",
          eligible_plans: null,
          max_redemptions: null,
        }),
      ),
    );
  });

  it("shows the amount label when the fixed-amount type is selected", async () => {
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));
    await waitFor(() => expect(screen.getByText("No promo codes yet.")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Promo type"), {
      target: { value: "fixed_amount" },
    });
    fireEvent.change(screen.getByLabelText("Promo value"), { target: { value: "999" } });
    expect(screen.getByText("Amount (cents)")).toBeInTheDocument();
    expect(screen.queryByLabelText("Target plan")).not.toBeInTheDocument();
  });

  it("surfaces create errors", async () => {
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));
    await waitFor(() => expect(screen.getByText("No promo codes yet.")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "DUP" } });
    mockApi.createAdminPromoCode.mockRejectedValueOnce(new Error("duplicate code"));
    fireEvent.click(screen.getByRole("button", { name: "Create promo code" }));

    await waitFor(() => expect(screen.getByText("duplicate code")).toBeInTheDocument());
  });

  it("falls back to a generic create error", async () => {
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));
    await waitFor(() => expect(screen.getByText("No promo codes yet.")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "DUP" } });
    mockApi.createAdminPromoCode.mockRejectedValueOnce("nope");
    fireEvent.click(screen.getByRole("button", { name: "Create promo code" }));

    await waitFor(() =>
      expect(screen.getByText("Could not create promo code.")).toBeInTheDocument(),
    );
  });

  it("toggles a promo code active state", async () => {
    listPromoCodesMock.mockResolvedValue([promo({ id: 3, code: "TOGGLE", active: true })]);
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(screen.getByText("TOGGLE")).toBeInTheDocument());
    updatePromoCodeMock.mockResolvedValueOnce(promo({ id: 3, code: "TOGGLE", active: false }));
    fireEvent.click(screen.getByRole("button", { name: "Retire" }));

    await waitFor(() =>
      expect(mockApi.updateAdminPromoCode).toHaveBeenCalledWith(3, { active: false }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reactivate" })).toBeInTheDocument(),
    );
  });

  it("leaves other codes untouched when toggling one in a multi-row list", async () => {
    listPromoCodesMock.mockResolvedValue([
      promo({ id: 3, code: "TOGGLE", active: true }),
      promo({ id: 4, code: "KEEP", active: true }),
    ]);
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(screen.getByText("TOGGLE")).toBeInTheDocument());
    updatePromoCodeMock.mockResolvedValueOnce(promo({ id: 3, code: "TOGGLE", active: false }));
    // Retire the first row; the second row's ternary hits the untouched branch.
    fireEvent.click(screen.getAllByRole("button", { name: "Retire" })[0]);

    await waitFor(() =>
      expect(mockApi.updateAdminPromoCode).toHaveBeenCalledWith(3, { active: false }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reactivate" })).toBeInTheDocument(),
    );
    // The untouched code still shows a Retire action.
    expect(screen.getByText("KEEP")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retire" })).toBeInTheDocument();
  });

  it("surfaces toggle errors", async () => {
    listPromoCodesMock.mockResolvedValue([promo({ id: 3, code: "TOGGLE" })]);
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(screen.getByText("TOGGLE")).toBeInTheDocument());
    mockApi.updateAdminPromoCode.mockRejectedValueOnce(new Error("cannot toggle"));
    fireEvent.click(screen.getByRole("button", { name: "Retire" }));

    await waitFor(() => expect(screen.getByText("cannot toggle")).toBeInTheDocument());
  });

  it("falls back to a generic toggle error", async () => {
    listPromoCodesMock.mockResolvedValue([promo({ id: 3, code: "TOGGLE" })]);
    renderWithClient(<AdminPromoCodesCard />);
    fireEvent.click(screen.getByRole("button", { name: "Load promo codes" }));

    await waitFor(() => expect(screen.getByText("TOGGLE")).toBeInTheDocument());
    mockApi.updateAdminPromoCode.mockRejectedValueOnce("nope");
    fireEvent.click(screen.getByRole("button", { name: "Retire" }));

    await waitFor(() =>
      expect(screen.getByText("Could not update promo code.")).toBeInTheDocument(),
    );
  });
});
