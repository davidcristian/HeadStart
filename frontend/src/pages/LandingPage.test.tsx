import { fireEvent, render, screen } from "@testing-library/react";
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
      screen.getByRole("heading", { name: "See new roles before the crowd." }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Create a free account" })[0]).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.getAllByRole("link", { name: "Sign in" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Go to app" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
  });

  it("shows product screenshots and switches showcase tabs", () => {
    renderLanding();

    expect(screen.getByRole("heading", { name: "See it in action" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Example push notification/i })).toHaveAttribute(
      "src",
      "/marketing/notification.png",
    );
    expect(
      screen.getByRole("tab", { name: "Searches", selected: true }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Jobs feed" }));
    expect(screen.getByRole("heading", { name: "Triage matches in one place" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /jobs feed/i })).toHaveAttribute(
      "src",
      "/marketing/jobs.png",
    );
  });

  it("links straight to the app when already signed in", () => {
    authState.user = { email: "user@example.com" };
    renderLanding();

    const appLinks = screen.getAllByRole("link", { name: "Go to app" });
    expect(appLinks.length).toBeGreaterThan(0);
    appLinks.forEach((link) => expect(link).toHaveAttribute("href", "/app"));
    expect(screen.getAllByRole("link", { name: "Open your dashboard" })[0]).toHaveAttribute(
      "href",
      "/app",
    );
    expect(screen.queryByRole("link", { name: "Create a free account" })).not.toBeInTheDocument();
  });
});
