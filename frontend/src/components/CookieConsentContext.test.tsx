import { render, renderHook, screen } from "@testing-library/react";
import { act } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { clearCookieConsent, getCookieConsent, setCookieConsent } from "../lib/cookieConsent";
import { CookieConsentProvider, useCookieConsent } from "./CookieConsentContext";

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <CookieConsentProvider>{children}</CookieConsentProvider>
    </MemoryRouter>
  );
}

describe("CookieConsentContext", () => {
  beforeEach(() => {
    clearCookieConsent();
  });

  it("throws when used outside a provider", () => {
    expect(() => renderHook(() => useCookieConsent())).toThrowError(
      "useCookieConsent must be used within CookieConsentProvider",
    );
  });

  it("starts visible with no prior choice", () => {
    const { result } = renderHook(() => useCookieConsent(), { wrapper });

    expect(result.current.choice).toBeNull();
    expect(result.current.visible).toBe(true);
  });

  it("persists a choice and hides the banner", () => {
    const { result } = renderHook(() => useCookieConsent(), { wrapper });

    act(() => result.current.setChoice("all"));

    expect(result.current.choice).toBe("all");
    expect(result.current.visible).toBe(false);
    expect(getCookieConsent()).toBe("all");
  });

  it("re-opens the banner via openCookieSettings after a choice was made", () => {
    setCookieConsent("essential");
    const { result } = renderHook(() => useCookieConsent(), { wrapper });

    expect(result.current.visible).toBe(false);
    act(() => result.current.openCookieSettings());
    expect(result.current.visible).toBe(true);

    // Choosing again closes the re-opened settings.
    act(() => result.current.setChoice("all"));
    expect(result.current.visible).toBe(false);
  });

  it("renders the consent banner as part of the provider tree", () => {
    render(
      <MemoryRouter>
        <CookieConsentProvider>
          <p>child content</p>
        </CookieConsentProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText("child content")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: /cookies on headstart/i })).toBeInTheDocument();
  });
});
