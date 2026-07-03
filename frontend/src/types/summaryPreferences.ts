/** Per-user AI provider preferences. */

export type SummaryProviderId = "heuristic" | "openai" | "gemini" | "anthropic";

export type AiPurposeId =
  "summary" | "cover_letter" | "resume_curation" | "email_classify" | "email_draft";

export type SummaryProviderOption = {
  id: SummaryProviderId;
  label: string;
  description: string;
  requires_api_key: boolean;
};

export type AiPurposeOption = {
  id: AiPurposeId;
  label: string;
  description: string;
  overridable: boolean;
};

export type PurposePreference = {
  selected_provider: SummaryProviderId | null;
  effective_provider: SummaryProviderId;
  selected_model: string | null;
  effective_model: string | null;
};

export type SummaryPreferences = {
  enabled: boolean;
  server_default_provider: string;
  selected_provider: SummaryProviderId | null;
  effective_provider: SummaryProviderId;
  has_custom_api_key: boolean;
  providers: SummaryProviderOption[];
  purposes: AiPurposeOption[];
  purpose_preferences: Record<string, PurposePreference>;
};

export type PurposePreferencePatch = {
  provider?: SummaryProviderId | null;
  model?: string | null;
};

export type SummaryPreferencesUpdate = {
  provider?: SummaryProviderId | null;
  api_key?: string | null;
  purpose_preferences?: Record<string, PurposePreferencePatch>;
};
