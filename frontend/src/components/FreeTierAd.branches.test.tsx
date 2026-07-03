import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent } from "../lib/cookieConsent";
import { renderWithClient } from "../test/renderWithClient";
import { CookieConsentProvider } from "./CookieConsentContext";
import { FreeTierAd } from "./FreeTierAd";

const mockMeta = vi.hoisted(() => vi.fn());

vi.mock("../hooks/queries", () => ({
  useMeta: () => mockMeta(),
}));

function renderAd(variant?: "sidebar" | "mobile") {
  return renderWithClient(
    <MemoryRouter>
      <CookieConsentProvider>
        <FreeTierAd variant={variant} />
      </CookieConsentProvider>
    </MemoryRouter>,
  );
}

describe("FreeTierAd branch coverage", () => {
  beforeEach(() => {
    clearCookieConsent();
  });

  it("renders nothing while meta is still loading (data undefined)", () => {
    mockMeta.mockReturnValue({ data: undefined });

    renderAd();

    expect(screen.queryByTestId("free-tier-ad")).not.toBeInTheDocument();
  });

  it("renders the compact mobile variant for free-tier users", () => {
    mockMeta.mockReturnValue({
      data: {
        plan: { show_ads: true },
        ads: { external_slot_url: null },
      },
    });

    renderAd("mobile");

    expect(screen.getByTestId("free-tier-ad")).toHaveClass("free-tier-ad--mobile");
  });
});
