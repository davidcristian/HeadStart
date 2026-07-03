/** Fastmail JMAP API token form for Settings → Inbox. */

import { Button, Field } from "../ui";
import type { FastmailConfig } from "../../types";

type SettingsInboxFastmailFormProps = {
  fastmailConfig: FastmailConfig;
  busy: boolean;
  onChange: (config: FastmailConfig) => void;
  onSave: () => void;
};

export function SettingsInboxFastmailForm({
  fastmailConfig,
  busy,
  onChange,
  onSave,
}: SettingsInboxFastmailFormProps) {
  return (
    <>
      <p>Or connect Fastmail with a JMAP API token:</p>
      <Field label="Fastmail email">
        <input
          value={fastmailConfig.email_address}
          onChange={(e) => onChange({ ...fastmailConfig, email_address: e.target.value })}
        />
      </Field>
      <Field
        label="Fastmail API token"
        hint="Create in Fastmail Settings → Privacy & Security → API tokens (Mail + Submission scopes)."
      >
        <input
          type="password"
          autoComplete="off"
          value={fastmailConfig.api_token}
          onChange={(e) => onChange({ ...fastmailConfig, api_token: e.target.value })}
        />
      </Field>
      <p>
        <Button type="button" onClick={onSave} disabled={busy}>
          Save Fastmail credentials
        </Button>
      </p>
    </>
  );
}
