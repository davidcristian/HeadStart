import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleTarget } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { TargetsPage } from "./TargetsPage";

describe("TargetsPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    renderWithClient(<TargetsPage />);

    expect(screen.getByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("No targets yet.")).toBeInTheDocument());
  });

  it("lists existing targets", async () => {
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText("My phone")).toBeInTheDocument());
    expect(screen.getByText(/"topic":"jobs"/)).toBeInTheDocument();
  });

  it("creates a target", async () => {
    renderWithClient(<TargetsPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("My phone"), {
      target: { value: "Work alerts" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create target" }));

    await waitFor(() => expect(mockApi.createTarget).toHaveBeenCalled());
    expect(mockApi.createTarget).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Work alerts", type: "discord" }),
    );
  });

  it("sends a test notification", async () => {
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText("My phone")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));

    await waitFor(() =>
      expect(screen.getByText("Test notification sent. Check your device.")).toBeInTheDocument(),
    );
  });

  it("deletes a target", async () => {
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText("My phone")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockApi.deleteTarget).toHaveBeenCalledWith(sampleTarget.id));
  });
});
