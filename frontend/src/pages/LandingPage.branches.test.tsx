import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookieConsent } from "../lib/cookieConsent";
import { renderPublicPage } from "../test/renderPublicPage";
import { LandingPage } from "./LandingPage";

const authState = vi.hoisted(() => ({ user: null as { email: string } | null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => authState }));

// Force the `find(...) ?? SHOWCASE[0]` fallback: the initial activeShowcase is
// "searches", so a SHOWCASE array without that id makes `find` return undefined.
vi.mock("./landing/content", () => ({
  INTEGRATIONS: ["Greenhouse"],
  STEPS: [{ step: "1", title: "Step one", body: "Body one" }],
  FEATURES: [{ title: "Feature one", body: "Body" }],
  FAQ: [{ q: "Question?", a: "Answer." }],
  SHOWCASE: [
    {
      id: "fallback",
      label: "Fallback",
      title: "Fallback showcase title",
      body: "Fallback body",
      image: "/marketing/fallback.png",
      alt: "Fallback alt",
    },
  ],
}));

describe("LandingPage showcase fallback branch", () => {
  beforeEach(() => {
    authState.user = null;
    clearCookieConsent();
  });

  it("falls back to the first showcase entry when the active id is missing", () => {
    render(renderPublicPage(<LandingPage />));

    // No showcase item has id "searches", so `find` returns undefined and the
    // `?? SHOWCASE[0]` fallback renders the first (only) entry.
    expect(screen.getByRole("heading", { name: "Fallback showcase title" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Fallback alt" })).toHaveAttribute(
      "src",
      "/marketing/fallback.png",
    );
  });
});
