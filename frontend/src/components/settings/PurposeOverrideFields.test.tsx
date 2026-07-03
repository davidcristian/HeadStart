import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  PurposeOverrideFields,
  SERVER_DEFAULT,
  emptyPurposeDrafts,
  type PurposeDraft,
} from "./PurposeOverrideFields";
import type { SummaryPreferences } from "../../types";

function makePreferences(overrides: Partial<SummaryPreferences> = {}): SummaryPreferences {
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
        id: "cover_letter",
        label: "Cover letters",
        description: "Apply dialog cover letters.",
        overridable: true,
      },
    ],
    purpose_preferences: {
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

const baseDraft: PurposeDraft = {
  provider: SERVER_DEFAULT,
  model: "",
  clearModel: false,
};

function renderFields(
  preferences: SummaryPreferences,
  draft: PurposeDraft = baseDraft,
  purposeId: SummaryPreferences["purposes"][number]["id"] = "cover_letter",
) {
  const onChange = vi.fn();
  render(
    <PurposeOverrideFields
      preferences={preferences}
      purposeId={purposeId}
      draft={draft}
      providerLabel={(id) => preferences.providers.find((p) => p.id === id)?.label ?? id}
      onChange={onChange}
    />,
  );
  return { onChange };
}

describe("PurposeOverrideFields", () => {
  it("renders nothing when the purpose is unknown", () => {
    const prefs = makePreferences();
    const { container } = render(
      <PurposeOverrideFields
        preferences={prefs}
        purposeId={"summary"}
        draft={baseDraft}
        providerLabel={(id) => id}
        onChange={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the purpose preference is missing", () => {
    const prefs = makePreferences({ purpose_preferences: {} });
    const { container } = render(
      <PurposeOverrideFields
        preferences={prefs}
        purposeId={"cover_letter"}
        draft={baseDraft}
        providerLabel={(id) => id}
        onChange={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the purpose block without model/checkbox when neither is set", () => {
    renderFields(makePreferences());
    expect(screen.getByText("Cover letters")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Cover letters provider" })).toBeInTheDocument();
    expect(screen.getByText("Model override (optional)")).toBeInTheDocument();
    expect(screen.queryByText("Remove saved model override")).not.toBeInTheDocument();
  });

  it("shows the effective model when present", () => {
    const prefs = makePreferences({
      purpose_preferences: {
        cover_letter: {
          selected_provider: "openai",
          effective_provider: "openai",
          selected_model: null,
          effective_model: "gpt-4o",
        },
      },
    });
    renderFields(prefs);
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("emits provider changes", () => {
    const { onChange } = renderFields(makePreferences());
    fireEvent.change(screen.getByRole("combobox", { name: "Cover letters provider" }), {
      target: { value: "openai" },
    });
    expect(onChange).toHaveBeenCalledWith({ provider: "openai" });
  });

  it("emits model changes and resets clearModel", () => {
    const { onChange } = renderFields(makePreferences());
    fireEvent.change(screen.getByRole("textbox", { name: "Cover letters model override" }), {
      target: { value: "gpt-4o-mini" },
    });
    expect(onChange).toHaveBeenCalledWith({ model: "gpt-4o-mini", clearModel: false });
  });

  it("shows the remove-model checkbox when a saved model exists and toggles it on", () => {
    const prefs = makePreferences({
      purpose_preferences: {
        cover_letter: {
          selected_provider: "openai",
          effective_provider: "openai",
          selected_model: "gpt-4o",
          effective_model: "gpt-4o",
        },
      },
    });
    const draft: PurposeDraft = { provider: "openai", model: "gpt-4o", clearModel: false };
    const { onChange } = renderFields(prefs, draft);

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith({ clearModel: true, model: "" });
  });

  it("restores the draft model when the remove-model checkbox is unchecked", () => {
    const prefs = makePreferences({
      purpose_preferences: {
        cover_letter: {
          selected_provider: "openai",
          effective_provider: "openai",
          selected_model: "gpt-4o",
          effective_model: "gpt-4o",
        },
      },
    });
    const draft: PurposeDraft = { provider: "openai", model: "gpt-4o", clearModel: true };
    const { onChange } = renderFields(prefs, draft);

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith({ clearModel: false, model: "gpt-4o" });
  });
});

describe("emptyPurposeDrafts", () => {
  it("uses the saved provider when a preference exists", () => {
    const prefs = makePreferences({
      purpose_preferences: {
        cover_letter: {
          selected_provider: "openai",
          effective_provider: "openai",
          selected_model: null,
          effective_model: null,
        },
      },
    });
    const drafts = emptyPurposeDrafts(prefs);
    expect(drafts.cover_letter).toEqual({ provider: "openai", model: "", clearModel: false });
  });

  it("falls back to the server default when no preference exists", () => {
    const prefs = makePreferences({ purpose_preferences: {} });
    const drafts = emptyPurposeDrafts(prefs);
    expect(drafts.cover_letter).toEqual({
      provider: SERVER_DEFAULT,
      model: "",
      clearModel: false,
    });
  });
});
