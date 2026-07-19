/** IMAP/SMTP manual mailbox form fields for Settings → Inbox. */

import { Button, Field } from "../ui";
import type { MailboxConfig } from "../../types";

type SettingsInboxImapFormProps = {
  imapConfig: MailboxConfig;
  busy: boolean;
  hasCredential: boolean;
  onChange: (config: MailboxConfig) => void;
  onSave: () => void;
  onTest: () => void;
  onDisconnect: () => void;
};

export function SettingsInboxImapForm({
  imapConfig,
  busy,
  hasCredential,
  onChange,
  onSave,
  onTest,
  onDisconnect,
}: SettingsInboxImapFormProps) {
  return (
    <>
      <p>Or configure IMAP + SMTP manually:</p>
      <Field label="IMAP host">
        <input
          value={imapConfig.imap_host}
          onChange={(e) => onChange({ ...imapConfig, imap_host: e.target.value })}
        />
      </Field>
      <Field label="IMAP user">
        <input
          value={imapConfig.imap_user}
          onChange={(e) => onChange({ ...imapConfig, imap_user: e.target.value })}
        />
      </Field>
      <Field label="IMAP password" hint="Write-only; not shown after save.">
        <input
          type="password"
          autoComplete="off"
          value={imapConfig.imap_password}
          onChange={(e) => onChange({ ...imapConfig, imap_password: e.target.value })}
        />
      </Field>
      <Field label="SMTP host">
        <input
          value={imapConfig.smtp_host}
          onChange={(e) => onChange({ ...imapConfig, smtp_host: e.target.value })}
        />
      </Field>
      <Field label="SMTP password" hint="Write-only; not shown after save.">
        <input
          type="password"
          autoComplete="off"
          value={imapConfig.smtp_password}
          onChange={(e) => onChange({ ...imapConfig, smtp_password: e.target.value })}
        />
      </Field>
      <p>
        <Button type="button" onClick={onSave} disabled={busy}>
          Save IMAP credentials
        </Button>{" "}
        <Button type="button" variant="ghost" onClick={onTest} disabled={busy}>
          Test connection
        </Button>{" "}
        {hasCredential ? (
          <Button type="button" variant="danger" onClick={onDisconnect} disabled={busy}>
            Disconnect
          </Button>
        ) : null}
      </p>
    </>
  );
}
