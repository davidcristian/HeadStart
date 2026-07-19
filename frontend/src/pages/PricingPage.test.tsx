import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent } from "../lib/cookieConsent";
import { renderPublicPage } from "../test/renderPublicPage";
import { PricingPage } from "./PricingPage";

const authState = vi.hoisted(() => ({ user: null as { email: string } | null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => authState }));

function renderPricing() {
  return render(renderPublicPage(<PricingPage />));
}

describe("PricingPage", () => {
  beforeEach(() => {
    authState.user = null;
    clearCookieConsent();
  });

  it("renders four plan cards and comparison table", () => {
    renderPricing();

    expect(screen.getByRole("heading", { name: "Pay for signal, not noise." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Starter" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Plus" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Team" })).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Pricing" })[0]).toHaveAttribute("href", "/pricing");
    expect(screen.getAllByRole("link", { name: "Get started free" })[0]).toHaveAttribute(
      "href",
      "/register",
    );
    expect(
      screen.getByText(/All prices are in EUR and include VAT where applicable/i),
    ).toBeInTheDocument();
  });

  it("switches displayed prices when toggling annual billing", () => {
    renderPricing();

    expect(screen.getByText(/9,99\s*€/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Annual/i }));
    expect(screen.getByText(/8,29\s*€/)).toBeInTheDocument();
    expect(screen.getByText(/Billed annually \(99,48\s*€\/yr\)/)).toBeInTheDocument();
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

  it("enables checkout for Starter, Plus, and Pro when signed in", () => {
    authState.user = { email: "user@example.com" };
    renderPricing();

    expect(screen.getByRole("button", { name: "Start with Starter" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Start with Plus" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Start with Pro" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Coming soon" })).not.toBeInTheDocument();
  });
});
