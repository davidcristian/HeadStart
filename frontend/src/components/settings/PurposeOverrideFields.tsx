/** Per-task AI provider/model override fields. */

import { Field } from "../ui";
import type { AiPurposeId, SummaryPreferences } from "../../types";

const SERVER_DEFAULT = "__server_default__";

export type PurposeDraft = {
  provider: string;
  model: string;
  clearModel: boolean;
};

type PurposeOverrideFieldsProps = {
  preferences: SummaryPreferences;
  purposeId: AiPurposeId;
  draft: PurposeDraft;
  providerLabel: (providerId: string) => string;
  onChange: (patch: Partial<PurposeDraft>) => void;
};

export function PurposeOverrideFields({
  preferences,
  purposeId,
  draft,
  providerLabel,
  onChange,
}: PurposeOverrideFieldsProps) {
  const purpose = preferences.purposes.find((item) => item.id === purposeId);
  const pref = preferences.purpose_preferences[purposeId];
  if (!purpose || !pref) return null;

  return (
    <div className="settings-purpose-block">
      <h4>{purpose.label}</h4>
      <p className="muted">{purpose.description}</p>
      <p className="muted">
        Active: <strong>{providerLabel(pref.effective_provider)}</strong>
        {pref.effective_model ? (
          <>
            {" "}
            · model <code>{pref.effective_model}</code>
          </>
        ) : null}
      </p>
      <Field label="Provider">
        <select
          value={draft.provider}
          onChange={(e) => onChange({ provider: e.target.value })}
          aria-label={`${purpose.label} provider`}
        >
          <option value={SERVER_DEFAULT}>Use global default</option>
          {preferences.providers.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </Field>
      <Field
        label="Model override (optional)"
        hint="Leave blank to use the deployment default for the selected provider."
      >
        <input
          type="text"
          aria-label={`${purpose.label} model override`}
          placeholder={pref.effective_model ?? "gpt-4o-mini"}
          value={draft.model}
          onChange={(e) => onChange({ model: e.target.value, clearModel: false })}
        />
        {pref.selected_model ? (
          <p>
            <label>
              <input
                type="checkbox"
                checked={draft.clearModel}
                onChange={(e) =>
                  onChange({
                    clearModel: e.target.checked,
                    model: e.target.checked ? "" : draft.model,
                  })
                }
              />{" "}
              Remove saved model override
            </label>
          </p>
        ) : null}
      </Field>
    </div>
  );
}

export function emptyPurposeDrafts(
  preferences: SummaryPreferences,
): Record<AiPurposeId, PurposeDraft> {
  const drafts = {} as Record<AiPurposeId, PurposeDraft>;
  for (const purpose of preferences.purposes) {
    const pref = preferences.purpose_preferences[purpose.id];
    drafts[purpose.id] = {
      provider: pref?.selected_provider ?? SERVER_DEFAULT,
      model: "",
      clearModel: false,
    };
  }
  return drafts;
}

export { SERVER_DEFAULT };
