import { mockApi } from "../../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { MockedFunction } from "vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../../test/renderWithClient";
import { SettingsSummaryCard } from "./SettingsSummaryCard";
import type { SummaryPreferences, SummaryPreferencesUpdate } from "../../types";

// The shared mockApi infers narrow literal return types; treat these two mocks as
// the real API signatures so `SummaryPreferences` values are assignable everywhere.
const getSummaryPreferences = mockApi.getSummaryPreferences as unknown as MockedFunction<
  () => Promise<SummaryPreferences>
>;
const updateSummaryPreferences = mockApi.updateSummaryPreferences as unknown as MockedFunction<
  (data: SummaryPreferencesUpdate) => Promise<SummaryPreferences>
>;

function enabledPreferences(overrides: Partial<SummaryPreferences> = {}): SummaryPreferences {
  return {
    enabled: true,
    server_default_provider: "heuristic",
    selected_provider: null,
    effective_provider: "heuristic",
    has_custom_api_key: false,
    providers: [
      {
        id: "heuristic",
        label: "Built-in",
        description: "Offline blurbs.",
        requires_api_key: false,
      },
      {
        id: "openai",
        label: "OpenAI",
        description: "OpenAI-compatible API.",
        requires_api_key: true,
      },
    ],
    purposes: [
      {
        id: "summary",
        label: "Job match summaries",
        description: "Blurbs in notifications.",
        overridable: false,
      },
      {
        id: "cover_letter",
        label: "Cover letters",
        description: "Apply dialog cover letters.",
        overridable: true,
      },
    ],
    purpose_preferences: {
      summary: {
        selected_provider: null,
        effective_provider: "heuristic",
        selected_model: null,
        effective_model: null,
      },
      cover_letter: {
        selected_provider: null,
        effective_provider: "heuristic",
        selected_model: null,
        effective_model: null,
      },
    },
    ...overrides,
  };
}

describe("SettingsSummaryCard (save)", () => {
  beforeEach(() => {
    vi.useRealTimers();
    getSummaryPreferences.mockReset();
    updateSummaryPreferences.mockReset();
    updateSummaryPreferences.mockImplementation(async () => enabledPreferences());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("saves global provider, api key and a per-task override, then clears the saved banner", async () => {
    vi.useFakeTimers();
    getSummaryPreferences.mockResolvedValue(
      enabledPreferences({
        purpose_preferences: {
          summary: {
            selected_provider: null,
            effective_provider: "heuristic",
            selected_model: null,
            effective_model: null,
          },
          cover_letter: {
            selected_provider: null,
            effective_provider: "heuristic",
            selected_model: "old-model",
            effective_model: "old-model",
          },
        },
      }),
    );
    updateSummaryPreferences.mockImplementation(async () =>
      enabledPreferences({ selected_provider: "openai", effective_provider: "openai" }),
    );

    renderWithClient(<SettingsSummaryCard />);
    await vi.waitFor(() => expect(screen.getByLabelText("Global AI provider")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Global AI provider"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("AI provider API key"), { target: { value: "sk-1" } });

    // Per-task override: change provider + set a model for the overridable "cover_letter".
    fireEvent.change(screen.getByLabelText("Cover letters provider"), {
      target: { value: "openai" },
    });
    fireEvent.change(screen.getByLabelText("Cover letters model override"), {
      target: { value: "gpt-4o" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save AI settings" }));

    await vi.waitFor(() => expect(updateSummaryPreferences).toHaveBeenCalled());
    const payload = updateSummaryPreferences.mock.calls[0][0] as {
      provider: string | null;
      api_key?: string;
      purpose_preferences?: Record<string, { provider?: string | null; model?: string | null }>;
    };
    expect(payload.provider).toBe("openai");
    expect(payload.api_key).toBe("sk-1");
    expect(payload.purpose_preferences?.cover_letter).toEqual({
      provider: "openai",
      model: "gpt-4o",
    });

    await vi.waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
    vi.advanceTimersByTime(2000);
    await vi.waitFor(() => expect(screen.queryByText("Saved.")).not.toBeInTheDocument());
  });

  it("clears the saved api key and a saved per-task model on save", async () => {
    getSummaryPreferences.mockResolvedValue(
      enabledPreferences({
        selected_provider: "openai",
        effective_provider: "openai",
        has_custom_api_key: true,
        purpose_preferences: {
          summary: {
            selected_provider: null,
            effective_provider: "heuristic",
            selected_model: null,
            effective_model: null,
          },
          cover_letter: {
            selected_provider: "openai",
            effective_provider: "openai",
            selected_model: "keep-me",
            effective_model: "keep-me",
          },
        },
      }),
    );

    renderWithClient(<SettingsSummaryCard />);
    await screen.findByLabelText("Global AI provider");

    // Remove the saved global API key (first checkbox in the API key field).
    const [apiKeyRemove, modelRemove] = screen.getAllByRole("checkbox");
    fireEvent.click(apiKeyRemove);
    // Remove the saved per-task model override (second checkbox, in the purpose block).
    fireEvent.click(modelRemove);

    fireEvent.click(screen.getByRole("button", { name: "Save AI settings" }));

    await waitFor(() => expect(updateSummaryPreferences).toHaveBeenCalled());
    const payload = updateSummaryPreferences.mock.calls[0][0] as {
      api_key?: string;
      purpose_preferences?: Record<string, { model?: string | null }>;
    };
    expect(payload.api_key).toBe("");
    expect(payload.purpose_preferences?.cover_letter).toEqual({ model: "" });
  });

  it("shows a save error banner when the update fails", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences());
    updateSummaryPreferences.mockRejectedValue(new Error("save failed"));
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByRole("button", { name: "Save AI settings" });
    fireEvent.click(screen.getByRole("button", { name: "Save AI settings" }));
    expect(await screen.findByText("save failed")).toBeInTheDocument();
  });

  it("shows a generic save error when a non-Error is thrown", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences());
    updateSummaryPreferences.mockRejectedValue("weird");
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByRole("button", { name: "Save AI settings" });
    fireEvent.click(screen.getByRole("button", { name: "Save AI settings" }));
    expect(await screen.findByText("Could not save AI settings.")).toBeInTheDocument();
  });

  it("sends provider null when the global default stays on server default", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences());
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByRole("button", { name: "Save AI settings" });
    fireEvent.click(screen.getByRole("button", { name: "Save AI settings" }));
    await waitFor(() => expect(updateSummaryPreferences).toHaveBeenCalled());
    const payload = updateSummaryPreferences.mock.calls[0][0] as { provider: string | null };
    expect(payload.provider).toBeNull();
  });

  it("falls back to the raw provider id when a provider is not in the catalog", async () => {
    // effective_provider references an id absent from `providers`, so providerLabel
    // must fall back to the raw id (`?? providerId`).
    getSummaryPreferences.mockResolvedValue(
      enabledPreferences({ effective_provider: "ghost-provider" as never }),
    );
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByText("Global default provider");
    // The global-default line renders the unknown id verbatim.
    expect(screen.getByText("ghost-provider")).toBeInTheDocument();
  });

  it("leaves selectedOption null when the selected provider is not in the catalog", async () => {
    // selected_provider (and thus the `provider` state) is a non-default id that is
    // absent from `providers`, so the `.find()` yields undefined -> `?? null`.
    getSummaryPreferences.mockResolvedValue(
      enabledPreferences({
        selected_provider: "ghost-provider" as never,
        effective_provider: "ghost-provider" as never,
      }),
    );
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByText("Global default provider");
    // No provider description or API-key field renders because selectedOption is null.
    expect(screen.queryByText("OpenAI-compatible API.")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("AI provider API key")).not.toBeInTheDocument();
  });
});
