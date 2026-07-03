import { mockApi, resetMockApi } from "../test/mockApi";
import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import type { DataRequestLog } from "../types";
import { AdminDataRequestsCard } from "./AdminDataRequestsCard";

function row(overrides: Partial<DataRequestLog> = {}): DataRequestLog {
  return {
    id: 1,
    user_id: 2,
    user_email: "member@example.com",
    request_type: "export",
    ip_address: "127.0.0.1",
    user_agent: "pytest",
    created_at: "2026-06-29T10:00:00Z",
    ...overrides,
  };
}

describe("AdminDataRequestsCard", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("shows only the intro while the request list is loading (no table yet)", () => {
    // Never-resolving query keeps requests.data undefined -> neither table nor
    // empty state renders.
    mockApi.listAdminDataRequests.mockReturnValue(new Promise(() => {}));
    renderWithClient(<AdminDataRequestsCard />);

    expect(screen.getByRole("heading", { name: "GDPR data requests" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No export or deletion requests recorded yet."),
    ).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no requests", async () => {
    mockApi.listAdminDataRequests.mockResolvedValue([]);
    renderWithClient(<AdminDataRequestsCard />);

    await waitFor(() =>
      expect(screen.getByText("No export or deletion requests recorded yet.")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders export and deletion rows with a placeholder for missing IPs", async () => {
    mockApi.listAdminDataRequests.mockResolvedValue([
      row({ id: 1, request_type: "export", ip_address: "10.0.0.1" }),
      row({ id: 2, request_type: "delete", ip_address: null, user_email: "gone@example.com" }),
    ]);
    renderWithClient(<AdminDataRequestsCard />);

    await waitFor(() => expect(screen.getByText("Data export")).toBeInTheDocument());
    expect(screen.getByText("Account deletion")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
    expect(screen.getByText("gone@example.com")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
