import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { AdminPage } from "./AdminPage";

const sampleAdminUser = {
  id: 1,
  email: "admin@example.com",
  is_admin: true,
  is_active: true,
  created_at: "2026-06-28T00:00:00Z",
};

const sampleMember = {
  id: 2,
  email: "member@example.com",
  is_admin: false,
  is_active: true,
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
  });

  it("renders the page and system stats", async () => {
    render(<AdminPage />);

    expect(screen.getByRole("heading", { name: "Admin" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Delivery failures")).toBeInTheDocument());
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("lists users and recent scrape errors", async () => {
    render(<AdminPage />);

    await waitFor(() => expect(screen.getByText("Broken search")).toBeInTheDocument());
    expect(screen.getAllByText("member@example.com").length).toBeGreaterThan(0);
    expect(screen.getByText("timeout")).toBeInTheDocument();
  });

  it("deactivates a user", async () => {
    render(<AdminPage />);

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
