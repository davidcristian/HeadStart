import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import type { PromoValidation } from "../types";
import { PromoCodeField } from "./PromoCodeField";

const validation: PromoValidation = {
  code: "LAUNCH20",
  promo_type: "percent_off",
  description: "20% off",
  trial_days: null,
  percent_off: 20,
  amount_off_cents: null,
  plan_target: null,
};

describe("PromoCodeField", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("uppercases input and disables Apply while empty", () => {
    const onApplied = vi.fn();
    renderWithClient(<PromoCodeField onApplied={onApplied} />);

    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "launch20" } });
    expect(screen.getByLabelText("Promo code")).toHaveValue("LAUNCH20");
    expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled();
  });

  it("keeps Apply disabled and never validates for whitespace-only input", () => {
    const onApplied = vi.fn();
    renderWithClient(<PromoCodeField onApplied={onApplied} />);

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "   " } });
    const apply = screen.getByRole("button", { name: "Apply" });
    expect(apply).toBeDisabled();

    // A disabled button does not fire onClick, so validation is never attempted.
    fireEvent.click(apply);
    expect(mockApi.validatePromoCode).not.toHaveBeenCalled();
    expect(onApplied).not.toHaveBeenCalled();
  });

  it("validates a code and reports it applied, then removes it", async () => {
    const onApplied = vi.fn();
    mockApi.validatePromoCode.mockResolvedValueOnce(
      validation as Awaited<ReturnType<typeof mockApi.validatePromoCode>>,
    );
    renderWithClient(<PromoCodeField onApplied={onApplied} />);

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "LAUNCH20" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("20% off"));
    expect(mockApi.validatePromoCode).toHaveBeenCalledWith("LAUNCH20");
    expect(onApplied).toHaveBeenCalledWith(validation);

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(onApplied).toHaveBeenLastCalledWith(null);
    expect(screen.getByLabelText("Promo code")).toHaveValue("");
  });

  it("shows an error when validation rejects with an Error", async () => {
    const onApplied = vi.fn();
    mockApi.validatePromoCode.mockRejectedValueOnce(new Error("Expired code"));
    renderWithClient(<PromoCodeField onApplied={onApplied} />);

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "OLD" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(screen.getByText("Expired code")).toBeInTheDocument());
    expect(onApplied).toHaveBeenCalledWith(null);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("falls back to a generic error when the rejection is not an Error", async () => {
    const onApplied = vi.fn();
    mockApi.validatePromoCode.mockRejectedValueOnce("nope");
    renderWithClient(<PromoCodeField onApplied={onApplied} />);

    fireEvent.change(screen.getByLabelText("Promo code"), { target: { value: "OLD" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(screen.getByText("Invalid promo code.")).toBeInTheDocument());
  });

  it("disables the input and button when the parent disables the field", () => {
    const onApplied = vi.fn();
    renderWithClient(<PromoCodeField onApplied={onApplied} disabled />);

    expect(screen.getByLabelText("Promo code")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
  });
});
