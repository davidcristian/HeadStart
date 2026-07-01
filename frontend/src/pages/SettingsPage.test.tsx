import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import { CookieConsentProvider } from "../components/CookieConsentContext";
import { clearCookieConsent } from "../lib/cookieConsent";
import { SettingsPage } from "./SettingsPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const logout = vi.fn();

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      logout,
      user: {
        id: 1,
        email: "user@example.com",
        is_admin: false,
        is_active: true,
        plan: "free" as const,
        onboarding_completed_at: "2026-06-28T00:00:00Z",
        created_at: "2026-06-28T00:00:00Z",
      },
    }),
  };
});

describe("SettingsPage", () => {
  beforeEach(() => {
    resetMockApi();
    navigate.mockReset();
    logout.mockReset();
    clearCookieConsent();
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:export"),
      revokeObjectURL: vi.fn(),
    });
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

  it("renders account controls", () => {
    renderSettings();
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Billing" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Privacy & cookies" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export my data" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete my account" })).toBeInTheDocument();
  });

  it("downloads an export bundle", async () => {
    mockApi.exportMyData.mockResolvedValue({
      exported_at: "2026-06-28T12:00:00Z",
      format_version: 1,
      account: {
        id: 1,
        email: "user@example.com",
        is_admin: false,
        is_active: true,
        plan: "free",
        onboarding_completed_at: "2026-06-28T00:00:00Z",
        created_at: "2026-06-28T00:00:00Z",
      },
      sources: [],
      searches: [],
      targets: [],
      credentials: [],
      profile: null,
      jobs: [],
    });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: "Export my data" }));

    await waitFor(() => expect(mockApi.exportMyData).toHaveBeenCalled());
    expect(click).toHaveBeenCalled();
  });

  it("deletes the account after password confirmation", async () => {
    renderSettings();
    fireEvent.change(screen.getByLabelText("Confirm account deletion password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));

    await waitFor(() => expect(mockApi.deleteAccount).toHaveBeenCalledWith("password123"));
    expect(logout).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith("/");
  });
});
