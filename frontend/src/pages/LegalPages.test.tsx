import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImpressumPage } from "./ImpressumPage";
import { PrivacyPolicyPage } from "./PrivacyPolicyPage";
import { TermsOfUsePage } from "./TermsOfUsePage";

const authState = vi.hoisted(() => ({ user: null as { email: string } | null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => authState }));

describe("Legal pages", () => {
  beforeEach(() => {
    authState.user = null;
  });

  it("renders the privacy policy with footer links", () => {
    render(
      <MemoryRouter>
        <PrivacyPolicyPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByText(/Effective June 28, 2026/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Impressum" })).toHaveAttribute("href", "/impressum");
    expect(screen.getByRole("link", { name: "Pricing" })).toHaveAttribute("href", "/pricing");
  });

  it("renders the terms of use", () => {
    render(
      <MemoryRouter>
        <TermsOfUsePage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Terms of Use" })).toBeInTheDocument();
    expect(screen.getByText(/Effective June 28, 2026/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Impressum" })).toHaveAttribute("href", "/impressum");
    expect(screen.getByRole("link", { name: "Pricing" })).toHaveAttribute("href", "/pricing");
  });

  it("renders the impressum with placeholder legal sections", () => {
    render(
      <MemoryRouter>
        <ImpressumPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Impressum" })).toBeInTheDocument();
    expect(screen.getByText(/Effective June 29, 2026/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Diensteanbieter" })).toBeInTheDocument();
    expect(screen.getByText(/\[Firmenname \/ Name des Betreibers\]/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Impressum" })).toHaveAttribute("href", "/impressum");
  });
});
