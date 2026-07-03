/** Settings card for per-user AI provider preferences (Pro). */

import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { Banner, Button, Card, Field } from "../ui";
import type { AiPurposeId, SummaryPreferences, SummaryProviderId } from "../../types";
import {
  PurposeOverrideFields,
  SERVER_DEFAULT,
  emptyPurposeDrafts,
  type PurposeDraft,
} from "./PurposeOverrideFields";

function providerLabel(preferences: SummaryPreferences, providerId: string): string {
  const match = preferences.providers.find((option) => option.id === providerId);
  return match?.label ?? providerId;
}

export function SettingsSummaryCard() {
  const [preferences, setPreferences] = useState<SummaryPreferences | null>(null);
  const [loadError, setLoadError] = useState<string>();
  const [saveError, setSaveError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [provider, setProvider] = useState<string>(SERVER_DEFAULT);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [purposeDrafts, setPurposeDrafts] = useState<Record<AiPurposeId, PurposeDraft>>(
    {} as Record<AiPurposeId, PurposeDraft>,
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getSummaryPreferences();
        if (!cancelled) {
          setPreferences(data);
          setProvider(data.selected_provider ?? SERVER_DEFAULT);
          setPurposeDrafts(emptyPurposeDrafts(data));
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Could not load AI settings.");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedOption = useMemo(() => {
    if (!preferences || provider === SERVER_DEFAULT) return null;
    return preferences.providers.find((option) => option.id === provider) ?? null;
  }, [preferences, provider]);

  function updatePurposeDraft(purposeId: AiPurposeId, patch: Partial<PurposeDraft>) {
    setPurposeDrafts((current) => ({
      ...current,
      [purposeId]: { ...current[purposeId], ...patch },
    }));
  }

  async function save() {
    // The "Save AI settings" button only renders inside the `preferences.enabled`
    // branch, so `preferences` is always present and enabled here.
    setSaveError(undefined);
    setSaved(false);
    setSaving(true);
    try {
      const purpose_preferences: Record<
        string,
        { provider?: SummaryProviderId | null; model?: string | null }
      > = {};

      for (const purpose of preferences!.purposes) {
        if (!purpose.overridable) continue;
        const draft = purposeDrafts[purpose.id];
        const saved = preferences!.purpose_preferences[purpose.id];
        const patch: { provider?: SummaryProviderId | null; model?: string | null } = {};

        const nextProvider =
          draft.provider === SERVER_DEFAULT ? null : (draft.provider as SummaryProviderId);
        if (nextProvider !== (saved?.selected_provider ?? null)) {
          patch.provider = nextProvider;
        }

        if (draft.clearModel) {
          patch.model = "";
        } else if (draft.model.trim()) {
          patch.model = draft.model.trim();
        }

        if (Object.keys(patch).length > 0) {
          purpose_preferences[purpose.id] = patch;
        }
      }

      const payload: {
        provider: SummaryProviderId | null;
        api_key?: string;
        purpose_preferences?: typeof purpose_preferences;
      } = {
        provider: provider === SERVER_DEFAULT ? null : (provider as SummaryProviderId),
      };
      if (clearApiKey) {
        payload.api_key = "";
      } else if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }
      if (Object.keys(purpose_preferences).length > 0) {
        payload.purpose_preferences = purpose_preferences;
      }

      const updated = await api.updateSummaryPreferences(payload);
      setPreferences(updated);
      setProvider(updated.selected_provider ?? SERVER_DEFAULT);
      setPurposeDrafts(emptyPurposeDrafts(updated));
      setApiKey("");
      setClearApiKey(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save AI settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <Card title="AI models">
        <Banner kind="error">{loadError}</Banner>
      </Card>
    );
  }

  if (!preferences) {
    return (
      <Card title="AI models">
        <p className="muted">Loading AI settings…</p>
      </Card>
    );
  }

  return (
    <Card title="AI models">
      <p>
        Choose which models HeadStart uses for job summaries, cover letters, and future inbox
        automation. Per-task overrides inherit the global default unless you set one.
      </p>

      {!preferences.enabled ? (
        <p>
          Custom AI providers are available on the <strong>Pro</strong> plan.{" "}
          <a href="/pricing">Upgrade to Pro</a> to configure them.
        </p>
      ) : (
        <>
          <p className="muted">
            Global default:{" "}
            <strong>{providerLabel(preferences, preferences.effective_provider)}</strong>
            {preferences.selected_provider ? null : (
              <>
                {" "}
                (server default: {providerLabel(preferences, preferences.server_default_provider)})
              </>
            )}
          </p>
          {saved ? <Banner kind="success">Saved.</Banner> : null}
          {saveError ? <Banner kind="error">{saveError}</Banner> : null}
          <Field
            label="Global default provider"
            hint="Used for job match summaries and as the fallback for cover letters and future agents."
          >
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setApiKey("");
                setClearApiKey(false);
              }}
              aria-label="Global AI provider"
            >
              <option value={SERVER_DEFAULT}>
                Server default ({providerLabel(preferences, preferences.server_default_provider)})
              </option>
              {preferences.providers.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          {selectedOption ? <p className="muted">{selectedOption.description}</p> : null}
          {selectedOption?.requires_api_key ? (
            <Field
              label="API key (optional)"
              hint={
                preferences.has_custom_api_key && !apiKey && !clearApiKey
                  ? "A custom API key is saved. Enter a new key to replace it, or clear it to use the server's configured key."
                  : "Shared across hosted providers. Leave blank to keep the current key or use the server's configured key."
              }
            >
              <input
                type="password"
                autoComplete="off"
                aria-label="AI provider API key"
                placeholder={preferences.has_custom_api_key ? "••••••••" : "sk-…"}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setClearApiKey(false);
                }}
              />
              {preferences.has_custom_api_key ? (
                <p>
                  <label>
                    <input
                      type="checkbox"
                      checked={clearApiKey}
                      onChange={(e) => {
                        setClearApiKey(e.target.checked);
                        if (e.target.checked) setApiKey("");
                      }}
                    />{" "}
                    Remove saved API key
                  </label>
                </p>
              ) : null}
            </Field>
          ) : null}

          <h3>Per-task overrides</h3>
          <p className="muted">
            Optional. Leave a task on &quot;Use global default&quot; to inherit the provider above.
          </p>
          {preferences.purposes
            .filter((purpose) => purpose.overridable)
            .map((purpose) => (
              <PurposeOverrideFields
                key={purpose.id}
                preferences={preferences}
                purposeId={purpose.id}
                draft={purposeDrafts[purpose.id]}
                providerLabel={(id) => providerLabel(preferences, id)}
                onChange={(patch) => updatePurposeDraft(purpose.id, patch)}
              />
            ))}

          <p>
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? "Saving…" : "Save AI settings"}
            </Button>
          </p>
        </>
      )}
    </Card>
  );
}
