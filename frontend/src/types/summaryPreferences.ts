/** Per-user AI summary provider preferences. */

export type SummaryProviderId = "heuristic" | "openai" | "gemini" | "anthropic";

export type SummaryProviderOption = {
  id: SummaryProviderId;
  label: string;
  description: string;
  requires_api_key: boolean;
};

export type SummaryPreferences = {
  enabled: boolean;
  server_default_provider: string;
  selected_provider: SummaryProviderId | null;
  effective_provider: SummaryProviderId;
  has_custom_api_key: boolean;
  providers: SummaryProviderOption[];
};

export type SummaryPreferencesUpdate = {
  provider?: SummaryProviderId | null;
  api_key?: string | null;
};
