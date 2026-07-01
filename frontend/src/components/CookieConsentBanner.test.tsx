import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { clearCookieConsent } from "../lib/cookieConsent";
import { CookieConsentProvider } from "./CookieConsentContext";

function renderConsent() {
  return render(
    <MemoryRouter>
      <CookieConsentProvider>
        <p>Page content</p>
      </CookieConsentProvider>
    </MemoryRouter>,
  );
}

describe("CookieConsentBanner", () => {
  beforeEach(() => {
    clearCookieConsent();
  });

  it("shows the banner until the visitor chooses", () => {
    renderConsent();

    expect(screen.getByRole("dialog", { name: /cookies on headstart/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute("href", "/privacy");
  });

  it("hides after essential-only consent", () => {
    renderConsent();

    fireEvent.click(screen.getByRole("button", { name: "Essential only" }));

    expect(screen.queryByRole("dialog", { name: /cookies on headstart/i })).not.toBeInTheDocument();
  });

  it("hides after accept-all consent", () => {
    renderConsent();

    fireEvent.click(screen.getByRole("button", { name: "Accept all" }));

    expect(screen.queryByRole("dialog", { name: /cookies on headstart/i })).not.toBeInTheDocument();
  });
});
