/** Manage notification targets (e.g. ntfy topics) and send test pushes. */

import { useState } from "react";
import { api } from "../api";
import { JsonEditor } from "../components/JsonEditor";
import { Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import type { Json } from "../types";

const NTFY_DEFAULT: Json = {
  server_url: "https://ntfy.sh",
  topic: "jobnotifier-change-me",
  priority: "default",
};

export function TargetsPage() {
  const targets = useAsync(() => api.listTargets(), []);
  const meta = useAsync(() => api.meta(), []);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [config, setConfig] = useState<Json>(NTFY_DEFAULT);
  const [configValid, setConfigValid] = useState(true);

  const types = meta.data?.notifiers ?? [];
  const effectiveType = type || types[0] || "";

  async function create() {
    setError(undefined);
    try {
      await api.createTarget({ name, type: effectiveType, config });
      setName("");
      setConfig(NTFY_DEFAULT);
      targets.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function test(id: number) {
    setError(undefined);
    setNotice(undefined);
    try {
      const result = await api.testTarget(id);
      if (result.status === "sent") setNotice("Test notification sent. Check your device.");
      else setError(`Test failed: ${result.error ?? "unknown error"}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: number) {
    await api.deleteTarget(id);
    targets.reload();
  }

  return (
    <>
      <h1>Notifications</h1>

      <Card title="Add a notification target">
        {error && <Banner kind="error">{error}</Banner>}
        {notice && <Banner kind="success">{notice}</Banner>}
        <div className="form-grid">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="My phone" />
          </Field>
          <Field label="Type">
            <select value={effectiveType} onChange={(e) => setType(e.target.value)}>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Config (JSON)" hint="For ntfy: server_url, topic, priority.">
          <JsonEditor
            value={config}
            onChange={(v, valid) => {
              setConfig(v);
              setConfigValid(valid);
            }}
          />
        </Field>
        <Button onClick={create} disabled={!name || !effectiveType || !configValid}>
          Create target
        </Button>
      </Card>

      <Card title="All targets">
        {targets.loading && <p>Loading...</p>}
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
                    <Button variant="ghost" onClick={() => test(t.id)}>
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
