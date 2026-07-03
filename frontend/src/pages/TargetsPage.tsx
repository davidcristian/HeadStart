/** Manage notification targets (e.g. ntfy topics, email) and send test notifications. */

import { useEffect, useState } from "react";
import { JsonEditor } from "../components/JsonEditor";
import { PlanUsageHint } from "../components/PlanUsageHint";
import { Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useMeta, useTargets } from "../hooks/queries";
import { useCreateTarget, useDeleteTarget, useTestTarget } from "../hooks/mutations";
import { canAddResource } from "../lib/plan";
import type { Json } from "../types";

const TYPE_DEFAULTS: Record<string, Json> = {
  email: { to: "you@example.com" },
  ntfy: {
    server_url: "https://ntfy.sh",
    topic: "headstart-change-me",
    priority: "default",
  },
  slack: {
    webhook_url: "https://hooks.slack.com/services/T00/B00/xxxxxxxxxxxxxxxxxxxxxxxx",
  },
  discord: {
    webhook_url: "https://discord.com/api/webhooks/123456789/xxxxxxxxxxxxxxxxxxxxxxxx",
  },
  telegram: {
    bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    chat_id: "123456789",
  },
  webhook: {
    webhook_url: "https://example.com/hooks/headstart",
    secret: "optional-signing-key",
  },
};

const TYPE_HINTS: Record<string, string> = {
  email: "For email: to (recipient address). Requires SMTP_* env vars on the server.",
  ntfy: "For ntfy: server_url, topic, priority.",
  slack: "For Slack: webhook_url (incoming webhook URL from your Slack workspace).",
  discord: "For Discord: webhook_url (channel webhook URL from your Discord server).",
  telegram: "For Telegram: bot_token (from @BotFather) and chat_id (your user or group id).",
  webhook:
    "For webhook: webhook_url (HTTPS endpoint). Optional secret (HMAC-SHA256 in X-HeadStart-Signature) and headers.",
};

export function TargetsPage() {
  const targets = useTargets();
  const meta = useMeta();
  const createTarget = useCreateTarget();
  const deleteTarget = useDeleteTarget();
  const testTarget = useTestTarget();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [config, setConfig] = useState<Json>({});
  const [configValid, setConfigValid] = useState(true);

  const types = meta.data?.notifiers ?? [];
  const effectiveType = type || types[0] || "";
  const configHint = TYPE_HINTS[effectiveType] ?? "Channel-specific JSON config.";
  const plan = meta.data?.plan;
  const canCreate = plan ? canAddResource(plan, "targets") : true;

  useEffect(() => {
    if (!meta.data?.notifiers.length || type) return;
    const initial = meta.data.notifiers[0];
    setType(initial);
    setConfig(TYPE_DEFAULTS[initial] ?? {});
  }, [meta.data, type]);

  function onTypeChange(nextType: string) {
    setType(nextType);
    setConfig(TYPE_DEFAULTS[nextType] ?? {});
  }

  async function create() {
    setError(undefined);
    try {
      await createTarget.mutateAsync({ name, type: effectiveType, config });
      setName("");
      setConfig(TYPE_DEFAULTS[effectiveType] ?? {});
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function test(id: number, targetType: string) {
    setError(undefined);
    setNotice(undefined);
    try {
      const result = await testTarget.mutateAsync(id);
      if (result.status === "sent") {
        const message =
          targetType === "email"
            ? "Test notification sent. Check your inbox."
            : targetType === "slack"
              ? "Test notification sent. Check your Slack channel."
              : targetType === "discord"
                ? "Test notification sent. Check your Discord channel."
                : targetType === "telegram"
                  ? "Test notification sent. Check your Telegram chat."
                  : targetType === "webhook"
                    ? "Test notification sent. Check your webhook endpoint."
                    : "Test notification sent. Check your device.";
        setNotice(message);
      } else setError(`Test failed: ${result.error ?? "unknown error"}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: number) {
    await deleteTarget.mutateAsync(id);
  }

  return (
    <>
      <h1>Notifications</h1>

      <Card title="Add a notification target">
        {plan && <PlanUsageHint plan={plan} resource="targets" />}
        {error && <Banner kind="error">{error}</Banner>}
        {notice && <Banner kind="success">{notice}</Banner>}
        <div className="form-grid">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="My phone" />
          </Field>
          <Field label="Type">
            <select value={effectiveType} onChange={(e) => onTypeChange(e.target.value)}>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Config (JSON)" hint={configHint}>
          <JsonEditor
            value={config}
            onChange={(v, valid) => {
              setConfig(v);
              setConfigValid(valid);
            }}
          />
        </Field>
        <Button onClick={create} disabled={!name || !effectiveType || !configValid || !canCreate}>
          Create target
        </Button>
      </Card>

      <Card title="All targets">
        {targets.isPending && <p>Loading...</p>}
        {targets.data && targets.data.length === 0 && <EmptyState>No targets yet.</EmptyState>}
        {targets.data && targets.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Config</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {targets.data.map((t) => (
                <tr key={t.id}>
                  <td>
                    <strong>{t.name}</strong>
                  </td>
                  <td>
                    <code>{t.type}</code>
                  </td>
                  <td>
                    <code className="muted">{JSON.stringify(t.config)}</code>
                  </td>
                  <td className="row-actions">
                    <Button variant="ghost" onClick={() => test(t.id, t.type)}>
                      Send test
                    </Button>
                    <Button variant="danger" onClick={() => remove(t.id)}>
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
