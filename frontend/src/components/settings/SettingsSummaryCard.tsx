/** Settings card for per-user AI summary provider preferences (Pro). */

import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { Banner, Button, Card, Field } from "../ui";
import type { SummaryPreferences, SummaryProviderId } from "../../types";

const SERVER_DEFAULT = "__server_default__";

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

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getSummaryPreferences();
        if (!cancelled) {
          setPreferences(data);
          setProvider(data.selected_provider ?? SERVER_DEFAULT);
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Could not load summary settings.");
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

  async function save() {
    if (!preferences?.enabled) return;
    setSaveError(undefined);
    setSaved(false);
    setSaving(true);
    try {
      const payload: {
        provider: SummaryProviderId | null;
        api_key?: string;
      } = {
        provider: provider === SERVER_DEFAULT ? null : (provider as SummaryProviderId),
      };
      if (clearApiKey) {
        payload.api_key = "";
      } else if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }
      const updated = await api.updateSummaryPreferences(payload);
      setPreferences(updated);
      setProvider(updated.selected_provider ?? SERVER_DEFAULT);
      setApiKey("");
      setClearApiKey(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save summary settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <Card title="AI summaries">
        <Banner kind="error">{loadError}</Banner>
      </Card>
    );
  }

  if (!preferences) {
    return (
      <Card title="AI summaries">
        <p className="muted">Loading summary settings…</p>
      </Card>
    );
  }

  return (
    <Card title="AI summaries">
      <p>
        Choose how HeadStart writes the &quot;why this matches&quot; blurb on new jobs in
        notifications and the Jobs feed.
      </p>

      {!preferences.enabled ? (
        <p>
          AI summaries are available on the <strong>Pro</strong> plan.{" "}
          <a href="/pricing">Upgrade to Pro</a> to customize the provider.
        </p>
      ) : (
        <>
          <p className="muted">
            Active provider:{" "}
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
            label="Summary provider"
            hint="Pick a hosted LLM or use the built-in offline matcher. Leave on server default to follow the operator's deployment config."
          >
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setApiKey("");
                setClearApiKey(false);
              }}
              aria-label="Summary provider"
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
                  : "Leave blank to keep the current key or use the server's configured key."
              }
            >
              <input
                type="password"
                autoComplete="off"
                aria-label="Summary provider API key"
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
          <p>
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? "Saving…" : "Save summary settings"}
            </Button>
          </p>
        </>
      )}
    </Card>
  );
}
