import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import { AdminPage } from "./AdminPage";

const sampleAdminUser = {
  id: 1,
  email: "admin@example.com",
  is_admin: true,
  is_active: true,
  plan: "team" as const,
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

const sampleMember = {
  id: 2,
  email: "member@example.com",
  is_admin: false,
  is_active: true,
  plan: "free" as const,
  onboarding_completed_at: "2026-06-29T00:00:00Z",
  created_at: "2026-06-29T00:00:00Z",
};

const sampleStats = {
  users_total: 2,
  users_active: 2,
  searches_total: 3,
  searches_enabled: 2,
  searches_with_error: 1,
  sources_total: 2,
  seen_jobs_total: 10,
  deliveries_sent: 8,
  deliveries_failed: 1,
  recent_errors: [
    {
      search_id: 20,
      search_name: "Broken search",
      user_email: "member@example.com",
      last_error: "timeout",
      last_run_at: "2026-06-28T12:00:00Z",
    },
  ],
};

describe("AdminPage", () => {
  beforeEach(() => {
    resetMockApi();
    mockApi.me.mockResolvedValue(sampleAdminUser);
    mockApi.listAdminUsers.mockResolvedValue([sampleAdminUser, sampleMember]);
    mockApi.getAdminStats.mockResolvedValue(sampleStats);
    mockApi.listAdminDataRequests.mockResolvedValue([
      {
        id: 1,
        user_id: 2,
        user_email: "member@example.com",
        request_type: "export",
        ip_address: "127.0.0.1",
        user_agent: "pytest",
        created_at: "2026-06-29T10:00:00Z",
      },
    ]);
  });

  it("renders the page and system stats", async () => {
    renderWithClient(<AdminPage />);

    expect(screen.getByRole("heading", { name: "Admin" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Delivery failures")).toBeInTheDocument());
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("lists users and recent scrape errors", async () => {
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("Broken search")).toBeInTheDocument());
    expect(screen.getAllByText("member@example.com").length).toBeGreaterThan(0);
    expect(screen.getByText("timeout")).toBeInTheDocument();
  });

  it("lists GDPR data request audit rows", async () => {
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("Data export")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "GDPR data requests" })).toBeInTheDocument();
    expect(screen.getAllByText("member@example.com").length).toBeGreaterThan(0);
  });

  it("deactivates a user", async () => {
    renderWithClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText("Broken search")).toBeInTheDocument());
    const deactivate = screen
      .getAllByRole("button", { name: "Deactivate" })
      .find((button) => !button.hasAttribute("disabled"));
    expect(deactivate).toBeDefined();
    fireEvent.click(deactivate!);

    await waitFor(() =>
      expect(mockApi.updateAdminUser).toHaveBeenCalledWith(sampleMember.id, {
        is_active: false,
      }),
    );
  });
});
