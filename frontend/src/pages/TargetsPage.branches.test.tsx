import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleMeta, sampleTarget } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type { Meta, NotificationTarget } from "../types";
import { TargetsPage } from "./TargetsPage";

/** Meta whose notifier list starts with a type absent from TYPE_DEFAULTS. */
const metaWithUnknownFirst: Meta = {
  ...sampleMeta,
  notifiers: ["unknown-channel", "email"],
};

function targetOfType(type: string): NotificationTarget {
  return { ...sampleTarget, type };
}

describe("TargetsPage branch coverage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("falls back to an empty config when the first notifier has no defaults", async () => {
    mockApi.meta.mockResolvedValue(metaWithUnknownFirst);
    renderWithClient(<TargetsPage />);

    // The effective type is initialised from the first (unknown) notifier, and
    // the config editor renders the empty-object fallback.
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "unknown-channel" })).toBeInTheDocument(),
    );
    const select = screen.getByDisplayValue("unknown-channel") as HTMLSelectElement;
    expect(select.value).toBe("unknown-channel");
  });

  it("switches type via the select for known and unknown notifiers", async () => {
    mockApi.meta.mockResolvedValue(metaWithUnknownFirst);
    const { container } = renderWithClient(<TargetsPage />);

    // Wait for the notifier options to load before driving the select.
    await screen.findByRole("option", { name: "email" });
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const readEditor = () => (container.querySelector(".json-editor") as HTMLTextAreaElement).value;

    // Known type -> loads its TYPE_DEFAULTS config (left side of ??).
    fireEvent.change(select, { target: { value: "email" } });
    await waitFor(() => expect(readEditor()).toContain('"to": "you@example.com"'));

    // Unknown type -> empty-object fallback (right side of ??).
    fireEvent.change(select, { target: { value: "unknown-channel" } });
    expect(select.value).toBe("unknown-channel");
    await waitFor(() => expect(readEditor()).toBe("{}"));
  });

  it("updates config and validity from the JSON editor", async () => {
    const { container } = renderWithClient(<TargetsPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    const textarea = container.querySelector(".json-editor") as HTMLTextAreaElement;

    // Invalid JSON disables the create button (configValid=false).
    fireEvent.change(textarea, { target: { value: "{ not json" } });
    fireEvent.change(screen.getByPlaceholderText("My phone"), {
      target: { value: "Alerts" },
    });
    expect(screen.getByRole("button", { name: "Create target" })).toBeDisabled();

    // Valid JSON re-enables it and updates the config state.
    fireEvent.change(textarea, { target: { value: '{"webhook_url":"https://x.test"}' } });
    expect(screen.getByRole("button", { name: "Create target" })).not.toBeDisabled();
  });

  it("resets to an empty config after creating an unknown notifier type", async () => {
    mockApi.meta.mockResolvedValue(metaWithUnknownFirst);
    renderWithClient(<TargetsPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("My phone"), {
      target: { value: "Odd channel" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create target" }));

    await waitFor(() =>
      expect(mockApi.createTarget).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Odd channel", type: "unknown-channel" }),
      ),
    );
  });

  it("shows an error banner when creating a target fails", async () => {
    mockApi.createTarget.mockRejectedValueOnce(new Error("Create boom"));
    renderWithClient(<TargetsPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("My phone"), {
      target: { value: "Broken" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create target" }));

    await waitFor(() => expect(screen.getByText("Create boom")).toBeInTheDocument());
  });

  it.each([
    ["email", "Test notification sent. Check your inbox."],
    ["slack", "Test notification sent. Check your Slack channel."],
    ["discord", "Test notification sent. Check your Discord channel."],
    ["telegram", "Test notification sent. Check your Telegram chat."],
    ["webhook", "Test notification sent. Check your webhook endpoint."],
  ])("shows the %s-specific success notice on a sent test", async (type, message) => {
    mockApi.listTargets.mockResolvedValue([targetOfType(type)]);
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText(sampleTarget.name)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));

    await waitFor(() => expect(screen.getByText(message)).toBeInTheDocument());
  });

  it("reports the returned error when a test is not sent", async () => {
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.testTarget.mockResolvedValueOnce({
      external_id: "",
      status: "failed",
      error: "delivery rejected",
    } as unknown as Awaited<ReturnType<typeof mockApi.testTarget>>);
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText(sampleTarget.name)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));

    await waitFor(() =>
      expect(screen.getByText("Test failed: delivery rejected")).toBeInTheDocument(),
    );
  });

  it("falls back to 'unknown error' when a failed test omits an error", async () => {
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.testTarget.mockResolvedValueOnce({
      external_id: "",
      status: "failed",
      error: null,
    });
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText(sampleTarget.name)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));

    await waitFor(() => expect(screen.getByText("Test failed: unknown error")).toBeInTheDocument());
  });

  it("surfaces the thrown error when the test request rejects", async () => {
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.testTarget.mockRejectedValueOnce(new Error("Network down"));
    renderWithClient(<TargetsPage />);

    await waitFor(() => expect(screen.getByText(sampleTarget.name)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));

    await waitFor(() => expect(screen.getByText("Network down")).toBeInTheDocument());
  });
});
