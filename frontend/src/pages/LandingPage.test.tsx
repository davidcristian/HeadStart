import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LandingPage } from "./LandingPage";

const authState = vi.hoisted(() => ({ user: null as { email: string } | null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => authState }));

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  );
}

describe("LandingPage", () => {
  beforeEach(() => {
    authState.user = null;
  });

  it("shows the marketing hero and signup CTAs when logged out", () => {
    renderLanding();

    expect(
      screen.getByRole("heading", { name: "Never miss the job you actually want." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create a free account" })).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.getAllByRole("link", { name: "Sign in" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Go to app" })).not.toBeInTheDocument();
  });

  it("links straight to the app when already signed in", () => {
    authState.user = { email: "user@example.com" };
    renderLanding();

    const appLinks = screen.getAllByRole("link", { name: "Go to app" });
    expect(appLinks.length).toBeGreaterThan(0);
    appLinks.forEach((link) => expect(link).toHaveAttribute("href", "/app"));
    expect(screen.getByRole("link", { name: "Open your dashboard" })).toHaveAttribute(
      "href",
      "/app",
    );
    expect(screen.queryByRole("link", { name: "Create a free account" })).not.toBeInTheDocument();
  });
});
