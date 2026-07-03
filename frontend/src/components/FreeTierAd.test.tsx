import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent, setCookieConsent } from "../lib/cookieConsent";
import { sampleAccountPlan } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { FreeTierAd } from "./FreeTierAd";

const mockMeta = vi.hoisted(() => vi.fn());

vi.mock("../hooks/queries", () => ({
  useMeta: () => mockMeta(),
}));

function renderAd() {
  return renderWithClient(
    <MemoryRouter>
      <FreeTierAd />
    </MemoryRouter>,
  );
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

    expect(screen.getByTitle("Partner advertisement")).toHaveAttribute(
      "src",
      "https://ads.example.com/slot",
    );
  });
});
