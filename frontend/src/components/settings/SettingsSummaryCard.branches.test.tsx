import { mockApi } from "../../test/mockApi";
import { act, waitFor } from "@testing-library/react";
import type { MockedFunction } from "vitest";
import { beforeEach, describe, expect, it } from "vitest";
import { renderWithClient } from "../../test/renderWithClient";
import { SettingsSummaryCard } from "./SettingsSummaryCard";
import type { SummaryPreferences } from "../../types";

const getSummaryPreferences = mockApi.getSummaryPreferences as unknown as MockedFunction<
  () => Promise<SummaryPreferences>
>;

const preferences: SummaryPreferences = {
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
  ],
  purposes: [
    {
      id: "summary",
      label: "Job match summaries",
      description: "Blurbs in notifications.",
      overridable: false,
    },
  ],
  purpose_preferences: {
    summary: {
      selected_provider: null,
      effective_provider: "heuristic",
      selected_model: null,
      effective_model: null,
    },
  },
};

describe("SettingsSummaryCard (unmount races)", () => {
  beforeEach(() => {
    getSummaryPreferences.mockReset();
  });

  it("ignores preferences that resolve after unmount", async () => {
    let resolvePreferences!: (value: SummaryPreferences) => void;
    getSummaryPreferences.mockReturnValue(
      new Promise<SummaryPreferences>((resolve) => {
        resolvePreferences = resolve;
      }),
    );

    const { container, unmount } = renderWithClient(<SettingsSummaryCard />);
    await waitFor(() => expect(getSummaryPreferences).toHaveBeenCalled());
    unmount();
    await act(async () => {
      resolvePreferences(preferences);
    });

    expect(container).toBeEmptyDOMElement();
  });

  it("ignores a preferences failure that lands after unmount", async () => {
    let rejectPreferences!: (reason: Error) => void;
    getSummaryPreferences.mockReturnValue(
      new Promise<SummaryPreferences>((_resolve, reject) => {
        rejectPreferences = reject;
      }),
    );

    const { container, unmount } = renderWithClient(<SettingsSummaryCard />);
    await waitFor(() => expect(getSummaryPreferences).toHaveBeenCalled());
    unmount();
    await act(async () => {
      rejectPreferences(new Error("boom"));
    });

    expect(container).toBeEmptyDOMElement();
  });
});
