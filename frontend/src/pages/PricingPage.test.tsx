import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PricingPage } from "./PricingPage";

const authState = vi.hoisted(() => ({ user: null as { email: string } | null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => authState }));

function renderPricing() {
  return render(
    <MemoryRouter>
      <PricingPage />
    </MemoryRouter>,
  );
}

describe("PricingPage", () => {
  beforeEach(() => {
    authState.user = null;
  });

  it("renders plan cards and comparison table", () => {
    renderPricing();

    expect(screen.getByRole("heading", { name: "Pay for signal, not noise." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Team" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Pricing" })[0]).toHaveAttribute("href", "/pricing");
    expect(screen.getAllByRole("link", { name: "Get started free" })[0]).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("switches displayed prices when toggling annual billing", () => {
    renderPricing();

    expect(screen.getByText("$12")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Annual/i }));
    expect(screen.getByText("$10")).toBeInTheDocument();
    expect(screen.getByText("Billed annually ($120/yr)")).toBeInTheDocument();
  });

  it("links to the app when signed in", () => {
    authState.user = { email: "user@example.com" };
    renderPricing();

    expect(screen.getAllByRole("link", { name: "Go to app" })[0]).toHaveAttribute("href", "/app");
    expect(screen.getByRole("link", { name: "Open your dashboard" })).toHaveAttribute(
      "href",
      "/app",
    );
  });
});
