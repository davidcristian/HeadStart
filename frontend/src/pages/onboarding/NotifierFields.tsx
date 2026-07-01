/** Dynamic form fields for the selected notification channel. */

import { Field } from "../../components/ui";
import type { Json } from "../../types";
import { NOTIFIER_HINTS } from "./constants";

interface NotifierFieldsProps {
  notifierType: string;
  config: Json;
  onChange: (config: Json) => void;
}

export function NotifierFields({ notifierType, config, onChange }: NotifierFieldsProps) {
  if (notifierType === "ntfy") {
    return (
      <>
        <Field label="ntfy topic" hint={NOTIFIER_HINTS.ntfy}>
          <input
            value={String(config.topic ?? "")}
            onChange={(e) => onChange({ ...config, topic: e.target.value })}
            placeholder="my-job-alerts"
            required
          />
        </Field>
        <Field label="Server URL">
          <input
            value={String(config.server_url ?? "https://ntfy.sh")}
            onChange={(e) => onChange({ ...config, server_url: e.target.value })}
          />
        </Field>
      </>
    );
  }
  if (notifierType === "email") {
    return (
      <Field label="Recipient email" hint={NOTIFIER_HINTS.email}>
        <input
          type="email"
          value={String(config.to ?? "")}
          onChange={(e) => onChange({ ...config, to: e.target.value })}
          placeholder="you@example.com"
          required
        />
      </Field>
    );
  }
  if (notifierType === "slack" || notifierType === "discord") {
    return (
      <Field label="Webhook URL" hint={NOTIFIER_HINTS[notifierType]}>
        <input
          value={String(config.webhook_url ?? "")}
          onChange={(e) => onChange({ ...config, webhook_url: e.target.value })}
          placeholder="https://..."
          required
        />
      </Field>
    );
  }
  if (notifierType === "telegram") {
    return (
      <>
        <Field label="Bot token" hint={NOTIFIER_HINTS.telegram}>
          <input
            value={String(config.bot_token ?? "")}
            onChange={(e) => onChange({ ...config, bot_token: e.target.value })}
            required
          />
        </Field>
        <Field label="Chat id">
          <input
            value={String(config.chat_id ?? "")}
            onChange={(e) => onChange({ ...config, chat_id: e.target.value })}
            required
          />
        </Field>
      </>
    );
  }
  return (
    <Field label="Webhook URL" hint={NOTIFIER_HINTS.webhook}>
      <input
        value={String(config.webhook_url ?? "")}
        onChange={(e) => onChange({ ...config, webhook_url: e.target.value })}
        placeholder="https://..."
        required
      />
    </Field>
  );
}
