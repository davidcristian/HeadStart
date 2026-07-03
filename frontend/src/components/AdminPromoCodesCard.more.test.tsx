import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { Mock } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import type { PromoCode } from "../types";
import { AdminPromoCodesCard } from "./AdminPromoCodesCard";

// The shared mock infers narrow return types (empty-array / object literals),
// so re-view the promo-code mocks through their real API signatures. This keeps
// `PromoCode` the authoritative type for the resolved values below.
const listPromoCodesMock = mockApi.listAdminPromoCodes as unknown as Mock<
  () => Promise<PromoCode[]>
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

describe("AdminPromoCodesCard (toggle)", () => {
  beforeEach(() => {
    resetMockApi();
    mockApi.listAdminPromoCodes.mockResolvedValue([]);
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
