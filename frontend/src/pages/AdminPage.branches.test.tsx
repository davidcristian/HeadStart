import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import type { AdminStats, AdminUser } from "../types";
import { AdminPage } from "./AdminPage";

const admin: AdminUser = {
  id: 1,
  email: "admin@example.com",
  is_admin: true,
  is_active: true,
  plan: "pro",
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

const member: AdminUser = {
  ...admin,
  id: 2,
  email: "member@example.com",
  is_admin: false,
  plan: "free",
};

const cleanStats: AdminStats = {
  users_total: 1,
  users_active: 1,
  searches_total: 0,
  searches_enabled: 0,
  searches_with_error: 0,
  sources_total: 0,
  seen_jobs_total: 0,
  deliveries_sent: 0,
  deliveries_failed: 0,
  recent_errors: [],
};

describe("AdminPage branch coverage", () => {
  beforeEach(() => {
    resetMockApi();
    mockApi.me.mockResolvedValue(admin);
    mockApi.getAdminStats.mockResolvedValue(cleanStats);
    mockApi.listAdminUsers.mockResolvedValue([admin, member]);
    mockApi.listAdminDataRequests.mockResolvedValue([]);
  });

  it("shows loading and empty states when stats/users are absent", async () => {
    mockApi.listAdminUsers.mockResolvedValue([]);
    renderWithClient(<AdminPage />);

    // No recent scrape errors.
    await waitFor(() => expect(screen.getByText("No scrape errors recorded.")).toBeInTheDocument());
    // No users yet.
    expect(screen.getByText("No users yet.")).toBeInTheDocument();
  });

  it("surfaces an error when updating a user fails", async () => {
    mockApi.updateAdminUser.mockRejectedValueOnce(new Error("update blocked"));
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("member@example.com")).toBeInTheDocument());
    const activate = screen
      .getAllByRole("button", { name: "Deactivate" })
      .find((button) => !button.hasAttribute("disabled"));
    fireEvent.click(activate!);

    await waitFor(() => expect(screen.getByText("update blocked")).toBeInTheDocument());
  });

  it("promotes a member to admin and changes their plan", async () => {
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("member@example.com")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Make admin" }));
    await waitFor(() =>
      expect(mockApi.updateAdminUser).toHaveBeenCalledWith(member.id, { is_admin: true }),
    );

    fireEvent.change(screen.getByLabelText(`Plan for ${member.email}`), {
      target: { value: "starter" },
    });
    await waitFor(() =>
      expect(mockApi.updateAdminUser).toHaveBeenCalledWith(member.id, { plan: "starter" }),
    );
  });

  it("activates an inactive user via the Activate button", async () => {
    mockApi.listAdminUsers.mockResolvedValue([admin, { ...member, is_active: false }]);
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("member@example.com")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Activate" }));

    await waitFor(() =>
      expect(mockApi.updateAdminUser).toHaveBeenCalledWith(member.id, { is_active: true }),
    );
  });

  it("renders a dash for scrape errors without a last run timestamp", async () => {
    mockApi.getAdminStats.mockResolvedValue({
      ...cleanStats,
      searches_with_error: 1,
      recent_errors: [
        {
          search_id: 30,
          search_name: "Never ran",
          user_email: "member@example.com",
          last_error: "boom",
          last_run_at: null,
        },
      ],
    });
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("Never ran")).toBeInTheDocument());
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  it("falls back to -1 self id when the current user is unavailable", async () => {
    mockApi.me.mockRejectedValue(new Error("unauthorized"));
    renderWithClient(<AdminPage />);

    // Users still load even though `me` failed; no row is treated as self,
    // so every action button stays enabled.
    await waitFor(() => expect(screen.getByText("member@example.com")).toBeInTheDocument());
    const deactivateButtons = screen.getAllByRole("button", { name: "Deactivate" });
    expect(deactivateButtons).toHaveLength(2);
    deactivateButtons.forEach((button) => expect(button).not.toBeDisabled());
  });
});
