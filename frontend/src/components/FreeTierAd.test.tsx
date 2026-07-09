import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent, setCookieConsent } from "../lib/cookieConsent";
import { sampleAccountPlan } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { CookieConsentProvider } from "./CookieConsentContext";
import { FreeTierAd } from "./FreeTierAd";

const mockMeta = vi.hoisted(() => vi.fn());

vi.mock("../hooks/queries", () => ({
  useMeta: () => mockMeta(),
}));

function renderAd() {
  return renderWithClient(
    <MemoryRouter>
      <CookieConsentProvider>
        <FreeTierAd />
      </CookieConsentProvider>
    </MemoryRouter>,
  );
}

function withExternalSlot() {
  mockMeta.mockReturnValue({
    data: {
      plan: {
        ...sampleAccountPlan,
        plan: "free",
        effective_plan: "free",
        unlimited: false,
        show_ads: true,
      },
      ads: { external_slot_url: "https://ads.example.com/slot" },
    },
  });
}

describe("FreeTierAd", () => {
  beforeEach(() => {
    clearCookieConsent();
    mockMeta.mockReturnValue({
      data: {
        plan: {
          ...sampleAccountPlan,
          plan: "free",
          effective_plan: "free",
          unlimited: false,
          show_ads: true,
        },
        ads: { external_slot_url: null },
      },
    });
  });

  it("renders the upgrade promotion for free-tier users", () => {
    renderAd();

    expect(screen.getByTestId("free-tier-ad")).toBeInTheDocument();
    expect(screen.getByText(/go ad-free with starter/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view plans/i })).toHaveAttribute("href", "/pricing");
  });

  it("renders nothing for paid plans", () => {
    mockMeta.mockReturnValue({
      data: {
        plan: { ...sampleAccountPlan, show_ads: false },
        ads: { external_slot_url: null },
      },
    });

    renderAd();

    expect(screen.queryByTestId("free-tier-ad")).not.toBeInTheDocument();
  });

  it("prompts for cookie consent before loading a partner ad slot", () => {
    mockMeta.mockReturnValue({
      data: {
        plan: {
          ...sampleAccountPlan,
          plan: "free",
          effective_plan: "free",
          unlimited: false,
          show_ads: true,
        },
        ads: { external_slot_url: "https://ads.example.com/slot" },
      },
    });

    renderAd();

    expect(screen.getByText(/accept optional cookies/i)).toBeInTheDocument();
    expect(screen.queryByTitle("Partner advertisement")).not.toBeInTheDocument();
  });

  it("loads the partner iframe when optional cookies are accepted", () => {
    setCookieConsent("all");
    withExternalSlot();

    renderAd();

    const frame = screen.getByTitle("Partner advertisement");
    expect(frame).toHaveAttribute("src", "https://ads.example.com/slot");
    // FRO-20: never combine allow-scripts with allow-same-origin on untrusted embeds.
    expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-popups");
    expect(frame.getAttribute("sandbox")).not.toContain("allow-same-origin");
  });

  it("reveals the partner iframe reactively when consent is accepted, without a reload", () => {
    clearCookieConsent();
    withExternalSlot();

    renderAd();
    expect(screen.queryByTitle("Partner advertisement")).not.toBeInTheDocument();

    // Accepting via the banner updates CookieConsentContext; the ad must react.
    fireEvent.click(screen.getByRole("button", { name: "Accept all" }));

    expect(screen.getByTitle("Partner advertisement")).toBeInTheDocument();
  });
});
