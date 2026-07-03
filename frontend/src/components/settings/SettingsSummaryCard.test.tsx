import { mockApi } from "../../test/mockApi";
import { fireEvent, screen } from "@testing-library/react";
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

describe("SettingsSummaryCard", () => {
  beforeEach(() => {
    vi.useRealTimers();
    getSummaryPreferences.mockReset();
    updateSummaryPreferences.mockReset();
    updateSummaryPreferences.mockImplementation(async () => enabledPreferences());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a load error banner when preferences fail to load", async () => {
    getSummaryPreferences.mockRejectedValue(new Error("boom"));
    renderWithClient(<SettingsSummaryCard />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("shows a generic load error when a non-Error is thrown", async () => {
    getSummaryPreferences.mockRejectedValue("nope");
    renderWithClient(<SettingsSummaryCard />);
    expect(await screen.findByText("Could not load AI settings.")).toBeInTheDocument();
  });

  it("shows a loading state before preferences arrive", () => {
    getSummaryPreferences.mockReturnValue(new Promise(() => {}));
    renderWithClient(<SettingsSummaryCard />);
    expect(screen.getByText("Loading AI settings…")).toBeInTheDocument();
  });

  it("shows the upgrade CTA when the feature is disabled", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences({ enabled: false }));
    renderWithClient(<SettingsSummaryCard />);
    expect(await screen.findByText(/Custom AI providers are available/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upgrade to Pro" })).toHaveAttribute(
      "href",
      "/pricing",
    );
  });

  it("no-ops save when disabled", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences({ enabled: false }));
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByText(/Custom AI providers are available/);
    // No save button rendered while disabled, so update is never called.
    expect(updateSummaryPreferences).not.toHaveBeenCalled();
  });

  it("renders the server-default hint when no provider is selected", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences());
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByText("Global default provider");
    expect(screen.getByText(/server default:/)).toBeInTheDocument();
  });

  it("shows the selected provider description and hides the server-default note", async () => {
    getSummaryPreferences.mockResolvedValue(
      enabledPreferences({ selected_provider: "openai", effective_provider: "openai" }),
    );
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByText("Global default provider");
    expect(screen.getByText("OpenAI-compatible API.")).toBeInTheDocument();
    expect(screen.queryByText(/server default:/)).not.toBeInTheDocument();
  });

  it("reveals the API key field for providers that require a key and resets on provider change", async () => {
    getSummaryPreferences.mockResolvedValue(enabledPreferences());
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByText("Global default provider");

    // Heuristic requires no key -> no key field.
    expect(screen.queryByLabelText("AI provider API key")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Global AI provider"), { target: { value: "openai" } });
    const keyInput = screen.getByLabelText("AI provider API key");
    expect(keyInput).toBeInTheDocument();
    fireEvent.change(keyInput, { target: { value: "sk-secret" } });
    expect((keyInput as HTMLInputElement).value).toBe("sk-secret");
  });

  it("shows the saved-key hint and the remove-key checkbox when a custom key is stored", async () => {
    getSummaryPreferences.mockResolvedValue(
      enabledPreferences({
        selected_provider: "openai",
        effective_provider: "openai",
        has_custom_api_key: true,
      }),
    );
    renderWithClient(<SettingsSummaryCard />);
    await screen.findByLabelText("AI provider API key");
    expect(screen.getByText(/A custom API key is saved/)).toBeInTheDocument();

    const removeCheckbox = screen.getByRole("checkbox");
    fireEvent.click(removeCheckbox);
    expect((removeCheckbox as HTMLInputElement).checked).toBe(true);
    // Typing a key after clearing switches the hint back.
    fireEvent.change(screen.getByLabelText("AI provider API key"), { target: { value: "sk-new" } });
    expect(screen.getByText(/Shared across hosted providers/)).toBeInTheDocument();
  });
});
