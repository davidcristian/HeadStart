import { fireEvent, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "../types";
import { setCookieConsent } from "../lib/cookieConsent";
import { renderWithClient } from "../test/renderWithClient";
import { CookieConsentProvider } from "./CookieConsentContext";
import { Layout } from "./Layout";

const mockHealth = vi.hoisted(() => vi.fn());
const mockMeta = vi.hoisted(() => vi.fn());
const mockUseAuth = vi.hoisted(() => vi.fn());
const logout = vi.hoisted(() => vi.fn());

vi.mock("../hooks/queries", () => ({
  useHealth: () => mockHealth(),
  useMeta: () => mockMeta(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const adminUser: User = {
  id: 1,
  email: "admin@example.com",
  is_admin: true,
  is_active: true,
  plan: "pro",
  onboarding_completed_at: "2026-06-01T00:00:00Z",
  email_verified_at: "2026-06-01T00:00:00Z",
  created_at: "2026-06-01T00:00:00Z",
};

const memberUser: User = { ...adminUser, id: 2, email: "member@example.com", is_admin: false };

function renderLayout(initialPath = "/app/dashboard") {
  return renderWithClient(
    <MemoryRouter initialEntries={[initialPath]}>
      <CookieConsentProvider>
        <Layout />
      </CookieConsentProvider>
    </MemoryRouter>,
  );
}

function openSheet(): HTMLElement {
  fireEvent.click(screen.getByRole("button", { name: "More" }));
  return screen.getByRole("dialog", { name: "More navigation" });
}

beforeEach(() => {
  // Pre-set consent so the CookieConsentBanner (also role="dialog") stays hidden
  // and does not collide with the Layout "More" sheet dialog assertions.
  setCookieConsent("all");
  logout.mockClear();
  mockHealth.mockReturnValue({ data: undefined });
  mockMeta.mockReturnValue({ data: undefined });
  mockUseAuth.mockReturnValue({ user: memberUser, logout });
});

describe("Layout", () => {
  it("renders desktop nav, user box, and API-unreachable status for a non-admin user", () => {
    renderLayout();

    expect(screen.getAllByText("Jobs").length).toBeGreaterThan(0);
    // Non-admin: no Admin link anywhere.
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
    // User box shows plain email with no "(admin)" suffix.
    expect(screen.getByText("member@example.com")).toBeInTheDocument();
    expect(screen.queryByText(/\(admin\)/)).not.toBeInTheDocument();
    // health.data is undefined -> status-bad branch.
    expect(screen.getByText("API unreachable")).toBeInTheDocument();
  });

  it("shows the Admin link and (admin) suffix and healthy API status for an admin user", () => {
    mockUseAuth.mockReturnValue({ user: adminUser, logout });
    mockHealth.mockReturnValue({ data: { version: "1.2.3", environment: "test" } });

    renderLayout();

    expect(screen.getAllByRole("link", { name: "Admin" }).length).toBeGreaterThan(0);
    expect(screen.getByText(/admin@example\.com/)).toHaveTextContent("admin@example.com (admin)");
    expect(screen.getByText("API v1.2.3 - test")).toBeInTheDocument();
  });

  it("renders without a user box or footer email when user is null", () => {
    mockUseAuth.mockReturnValue({ user: null, logout });

    renderLayout();

    expect(screen.queryByText("member@example.com")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
    expect(screen.getByText("API unreachable")).toBeInTheDocument();
  });

  it("signs out from the sidebar footer", () => {
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("toggles the mobile More sheet open and closed via the nav button", () => {
    renderLayout();

    const moreButton = screen.getByRole("button", { name: "More" });
    expect(moreButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(moreButton);
    expect(moreButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("dialog", { name: "More navigation" })).toBeInTheDocument();

    fireEvent.click(moreButton);
    expect(moreButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the sheet when the backdrop is clicked but not when the sheet body is clicked", () => {
    const { container } = renderLayout();

    const dialog = openSheet();

    // Clicking inside the sheet stops propagation -> stays open.
    fireEvent.click(dialog);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Clicking the backdrop closes it.
    const backdrop = container.querySelector(".mobile-more-backdrop") as HTMLElement;
    fireEvent.click(backdrop);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the sheet via the Close button in the header", () => {
    renderLayout();

    const dialog = openSheet();

    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the sheet when a More nav link is followed", () => {
    renderLayout();

    const dialog = openSheet();

    fireEvent.click(within(dialog).getByRole("link", { name: "Settings" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the Admin link inside the sheet for admins and closes it when clicked", () => {
    mockUseAuth.mockReturnValue({ user: adminUser, logout });
    renderLayout();

    const dialog = openSheet();

    fireEvent.click(within(dialog).getByRole("link", { name: "Admin" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("omits the Admin link and footer from the sheet when there is no user", () => {
    mockUseAuth.mockReturnValue({ user: null, logout });
    renderLayout();

    const dialog = openSheet();

    expect(within(dialog).queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
    // No footer user email / sign out inside the sheet.
    expect(within(dialog).queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("signs out and closes the sheet from the sheet footer", () => {
    renderLayout();

    const dialog = openSheet();

    fireEvent.click(within(dialog).getByRole("button", { name: "Sign out" }));

    expect(logout).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("marks the active mobile primary nav link when its route is current", () => {
    renderLayout("/app/jobs");

    const jobsLinks = screen.getAllByRole("link", { name: "Jobs" });
    const mobileJobs = jobsLinks.find((el) => el.classList.contains("mobile-nav-link"));
    expect(mobileJobs).toHaveClass("active");
  });

  it("marks the active More-sheet nav link when its route is current", () => {
    renderLayout("/app/settings");

    const dialog = openSheet();
    expect(within(dialog).getByRole("link", { name: "Settings" })).toHaveClass("active");
  });

  it("marks the active Admin link inside the More sheet when on the admin route", () => {
    mockUseAuth.mockReturnValue({ user: adminUser, logout });
    renderLayout("/app/admin");

    const dialog = openSheet();
    expect(within(dialog).getByRole("link", { name: "Admin" })).toHaveClass("active");
  });

  it("closes the sheet on Escape via the focus trap", () => {
    renderLayout();

    openSheet();
    expect(screen.getByRole("dialog", { name: "More navigation" })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
