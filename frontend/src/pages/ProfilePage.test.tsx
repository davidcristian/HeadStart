import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleProfile } from "../test/fixtures";
import { ProfilePage } from "./ProfilePage";

describe("ProfilePage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty form", async () => {
    render(<ProfilePage />);

    expect(screen.getByRole("heading", { name: "Application profile" })).toBeInTheDocument();
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("");
    // No saved profile yet, so no clear button.
    expect(screen.queryByRole("button", { name: "Clear profile" })).not.toBeInTheDocument();
  });

  it("loads an existing profile into the form", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    render(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("Ada Lovelace"),
    );
    expect(screen.getByPlaceholderText("ada@example.com")).toHaveValue("ada@example.com");
    expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument();
  });

  it("saves the profile", async () => {
    render(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("Ada Lovelace"), {
      target: { value: "Grace Hopper" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(mockApi.saveProfile).toHaveBeenCalled());
    expect(mockApi.saveProfile).toHaveBeenCalledWith(
      expect.objectContaining({ full_name: "Grace Hopper" }),
    );
    await waitFor(() => expect(screen.getByText("Profile saved.")).toBeInTheDocument());
  });

  it("clears an existing profile", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    render(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear profile" }));

    await waitFor(() => expect(mockApi.deleteProfile).toHaveBeenCalled());
  });
});
