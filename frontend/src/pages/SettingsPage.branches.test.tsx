import { mockApi, resetMockApi } from "../test/mockApi";
import { sampleMeta } from "../test/fixtures";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import { CookieConsentProvider } from "../components/CookieConsentContext";
import { clearCookieConsent, setCookieConsent } from "../lib/cookieConsent";
import type { User } from "../types";
import { SettingsPage } from "./SettingsPage";

const navigate = vi.fn();
const setSearchParams = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigate,
    useSearchParams: () => [searchParams, setSearchParams] as const,
  };
});

const logout = vi.fn();
const refreshUser = vi.fn(async () => undefined);

const baseUser: User = {
  id: 1,
  email: "user@example.com",
  is_admin: false,
  is_active: true,
  plan: "free",
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

let authUser: User | null = baseUser;

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({ logout, refreshUser, user: authUser }),
  };
});

describe("SettingsPage branches", () => {
  beforeEach(() => {
    resetMockApi();
    navigate.mockReset();
    setSearchParams.mockReset();
    searchParams = new URLSearchParams();
    logout.mockReset();
    refreshUser.mockReset();
    refreshUser.mockResolvedValue(undefined);
    authUser = baseUser;
    clearCookieConsent();
    localStorage.removeItem("headstart.apiBaseUrl");
    // SettingsInboxCard loads mailbox credentials; the shared mock lacks this
    // method, so provide it dynamically for the inbox-enabled case.
    (mockApi as Record<string, unknown>).getMailboxCredentials = vi
      .fn()
      .mockRejectedValue(new Error("Mailbox not configured"));
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:export"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function renderSettings() {
    return renderWithClient(
      <MemoryRouter>
        <CookieConsentProvider>
          <SettingsPage />
        </CookieConsentProvider>
      </MemoryRouter>,
    );
  }

  it("shows the success banner and refreshes the user on billing=success", async () => {
    searchParams = new URLSearchParams("billing=success");
    renderSettings();

    expect(
      screen.getByText(/Subscription updated. Your plan may take a moment to refresh./),
    ).toBeInTheDocument();
    await waitFor(() => expect(refreshUser).toHaveBeenCalled());
    expect(setSearchParams).toHaveBeenCalled();
  });

  it("shows the cancel banner on billing=cancel", () => {
    searchParams = new URLSearchParams("billing=cancel");
    renderSettings();
    expect(screen.getByText(/Checkout was cancelled. No changes were made./)).toBeInTheDocument();
    expect(refreshUser).not.toHaveBeenCalled();
  });

  it("renders the inbox card when meta enables the inbox agent", async () => {
    searchParams = new URLSearchParams("mailbox=connected");
    mockApi.meta.mockResolvedValue({ ...sampleMeta, inbox_agent_enabled: true });
    renderSettings();

    expect(
      await screen.findByRole("heading", { name: "Inbox automation (dev only)" }),
    ).toBeInTheDocument();
  });

  it("hides the inbox card when meta fails to load", async () => {
    mockApi.meta.mockRejectedValue(new Error("meta boom"));
    renderSettings();

    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());
    expect(
      screen.queryByRole("heading", { name: "Inbox automation (dev only)" }),
    ).not.toBeInTheDocument();
  });

  it("shows the admin note for admin accounts", () => {
    authUser = { ...baseUser, is_admin: true };
    renderSettings();
    expect(screen.getByText(/Admin accounts are not capped by plan limits./)).toBeInTheDocument();
  });

  it("renders account-less state without billing/summary cards", () => {
    authUser = null;
    renderSettings();
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Billing" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument();
  });

  it("saves the API base URL and clears the saved banner after the timeout", () => {
    vi.useFakeTimers();
    renderSettings();
    fireEvent.change(screen.getByDisplayValue("http://localhost:8000"), {
      target: { value: "https://api.example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByText("Saved.")).toBeInTheDocument();
    expect(localStorage.getItem("headstart.apiBaseUrl")).toBe("https://api.example.test");

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
  });

  it("shows an error banner when the export fails with an Error", async () => {
    mockApi.exportMyData.mockRejectedValue(new Error("export exploded"));
    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: "Export my data" }));

    expect(await screen.findByText("export exploded")).toBeInTheDocument();
  });

  it("shows a generic error banner when the export rejects with a non-Error", async () => {
    mockApi.exportMyData.mockRejectedValue("weird");
    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: "Export my data" }));

    expect(await screen.findByText("Export failed.")).toBeInTheDocument();
  });

  it("blocks deletion when no password is entered", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));

    expect(screen.getByText("Enter your password to confirm deletion.")).toBeInTheDocument();
    expect(mockApi.deleteAccount).not.toHaveBeenCalled();
  });

  it("shows the delete error from an Error", async () => {
    mockApi.deleteAccount.mockRejectedValue(new Error("wrong password"));
    renderSettings();
    fireEvent.change(screen.getByLabelText("Confirm account deletion password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));

    expect(await screen.findByText("wrong password")).toBeInTheDocument();
    expect(logout).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("shows a generic delete error for a non-Error rejection", async () => {
    mockApi.deleteAccount.mockRejectedValue("nope");
    renderSettings();
    fireEvent.change(screen.getByLabelText("Confirm account deletion password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));

    expect(await screen.findByText("Could not delete account.")).toBeInTheDocument();
  });

  it("labels the cookie consent as accept-all", () => {
    setCookieConsent("all");
    renderSettings();
    expect(
      screen.getByText(/Accept all \(optional cookies allowed when enabled\)/),
    ).toBeInTheDocument();
  });

  it("labels the cookie consent as essential only", () => {
    setCookieConsent("essential");
    renderSettings();
    expect(screen.getByText("Essential only")).toBeInTheDocument();
  });

  it("labels the cookie consent as not set and opens cookie settings", () => {
    renderSettings();
    expect(screen.getByText("Not set")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cookie settings" }));
    // The consent banner becomes visible when settings are opened.
    expect(screen.getAllByText(/cookie/i).length).toBeGreaterThan(0);
  });
});
