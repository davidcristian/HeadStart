import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Plan } from "../../lib/pricing";
import { ComparisonCell, PlanCta } from "./PricingParts";

function planOf(overrides: Partial<Plan> = {}): Plan {
  return {
    id: "pro",
    name: "Pro",
    description: "Full toolkit",
    monthlyPrice: 9.99,
    annualPricePerMonth: 8.29,
    highlight: true,
    checkoutEnabled: true,
    cta: "Start with Pro",
    limits: { searches: "20", sources: "20", targets: "5" },
    features: [],
    ...overrides,
  };
}

function renderCta(node: React.ReactElement) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe("ComparisonCell", () => {
  it("renders a checkmark for an included boolean", () => {
    render(<ComparisonCell value={true} />);
    expect(screen.getByLabelText("Included")).toHaveTextContent("✓");
  });

  it("renders a cross for an excluded boolean", () => {
    render(<ComparisonCell value={false} />);
    expect(screen.getByLabelText("Not included")).toHaveTextContent("✗");
  });

  it("renders a plain string value", () => {
    render(<ComparisonCell value="20" />);
    expect(screen.getByText("20")).toBeInTheDocument();
  });
});

describe("PlanCta", () => {
  it("links to register for the free plan regardless of user", () => {
    renderCta(
      <PlanCta
        plan={planOf({ id: "free", highlight: false })}
        user={null}
        checkingOut={false}
        onCheckout={() => {}}
      />,
    );
    expect(screen.getByRole("link", { name: "Start with Pro" })).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("renders a checkout button for a signed-in user on a checkout-enabled plan", () => {
    const onCheckout = vi.fn();
    renderCta(
      <PlanCta
        plan={planOf()}
        user={{ email: "a@b.c" }}
        checkingOut={false}
        onCheckout={onCheckout}
      />,
    );
    const button = screen.getByRole("button", { name: "Start with Pro" });
    expect(button).toBeEnabled();
    button.click();
    expect(onCheckout).toHaveBeenCalled();
  });

  it("shows the redirecting label while checking out", () => {
    renderCta(
      <PlanCta plan={planOf()} user={{ email: "a@b.c" }} checkingOut onCheckout={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "Redirecting…" })).toBeDisabled();
  });

  it("shows a disabled Coming soon button for a signed-in user on a non-checkout plan", () => {
    renderCta(
      <PlanCta
        plan={planOf({ id: "plus", checkoutEnabled: false })}
        user={{ email: "a@b.c" }}
        checkingOut={false}
        onCheckout={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Coming soon" })).toBeDisabled();
  });

  it("links to register for a logged-out user on a paid plan", () => {
    renderCta(
      <PlanCta
        plan={planOf({ id: "starter", highlight: false })}
        user={null}
        checkingOut={false}
        onCheckout={() => {}}
      />,
    );
    expect(screen.getByRole("link", { name: "Start with Pro" })).toHaveAttribute(
      "href",
      "/register",
    );
  });
});
