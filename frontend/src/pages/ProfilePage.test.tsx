import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleProfile } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { ProfilePage } from "./ProfilePage";

describe("ProfilePage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty form", async () => {
    renderWithClient(<ProfilePage />);

    expect(screen.getByRole("heading", { name: "Application profile" })).toBeInTheDocument();
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("");
    // No saved profile yet, so no clear button.
    expect(screen.queryByRole("button", { name: "Clear profile" })).not.toBeInTheDocument();
  });

  it("loads an existing profile into the form", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderWithClient(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("Ada Lovelace"),
    );
    expect(screen.getByPlaceholderText("ada@example.com")).toHaveValue("ada@example.com");
    expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument();
  });

  it("saves the profile", async () => {
    renderWithClient(<ProfilePage />);
    // Wait for the initial fetch to settle (Save is disabled while pending) so the
    // populate-effect cannot overwrite the value we type below.
    await waitFor(() => expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled());

    fireEvent.change(screen.getByPlaceholderText("Ada Lovelace"), {
      target: { value: "Grace Hopper" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() =>
      expect(mockApi.saveProfile).toHaveBeenCalledWith(
        expect.objectContaining({ full_name: "Grace Hopper" }),
      ),
    );
    await waitFor(() => expect(screen.getByText("Profile saved.")).toBeInTheDocument());
  });

  it("clears an existing profile", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderWithClient(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear profile" }));

    await waitFor(() => expect(mockApi.deleteProfile).toHaveBeenCalled());
  });

  it("shows application history", async () => {
    mockApi.listApplicationLogs.mockResolvedValue([
      {
        id: 1,
        seen_job_id: 100,
        job_title: "Software Engineer",
        job_company: "ACME",
        job_url: "https://example.test/jobs/1",
        status: "dry_run",
        dry_run: true,
        error: null,
        payload: { email: "ada@example.com" },
        external_application_id: null,
        created_at: "2026-06-28T12:00:00Z",
      },
    ]);
    renderWithClient(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(screen.getByText("Preview")).toBeInTheDocument();
  });
});
