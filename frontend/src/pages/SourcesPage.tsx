/** Manage sources (job sites + which scraper handles them). */

import { useState } from "react";
import { api } from "../api";
import { JsonEditor } from "../components/JsonEditor";
import { Badge, Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import type { Json } from "../types";

export function SourcesPage() {
  const sources = useAsync(() => api.listSources(), []);
  const meta = useAsync(() => api.meta(), []);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const [name, setName] = useState("");
  const [adapter, setAdapter] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [config, setConfig] = useState<Json>({});
  const [configValid, setConfigValid] = useState(true);

  const adapters = meta.data?.scrapers ?? [];
  const effectiveAdapter = adapter || adapters[0] || "";

  async function create() {
    setError(undefined);
    try {
      await api.createSource({
        name,
        adapter_key: effectiveAdapter,
        base_url: baseUrl,
        default_config: config,
        enabled: true,
      });
      setName("");
      setBaseUrl("");
      setConfig({});
      sources.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: number) {
    await api.deleteSource(id);
    sources.reload();
  }

  async function toggle(id: number, enabled: boolean) {
    await api.updateSource(id, { enabled });
    sources.reload();
  }

  async function test(id: number) {
    setError(undefined);
    setNotice(undefined);
    try {
      const result = await api.testSource(id);
      if (!result.ok) {
        setError(result.error ?? "Source test failed");
        return;
      }
      const titles = result.sample.map((j) => j.title).join(", ");
      const preview = titles ? ` Sample: ${titles}.` : "";
      setNotice(`Found ${result.found} posting(s).${preview}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <h1>Sources</h1>

      <Card title="Add a source">
        {error && <Banner kind="error">{error}</Banner>}
        {notice && <Banner kind="success">{notice}</Banner>}
        <div className="form-grid">
          <Field label="Name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ACME Careers"
            />
          </Field>
          <Field label="Adapter" hint="Which scraper to use.">
            <select value={effectiveAdapter} onChange={(e) => setAdapter(e.target.value)}>
              {adapters.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Base URL">
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://..."
            />
          </Field>
        </div>
        <Field label="Default config (JSON)" hint='e.g. {"board_token": "acme", "company": "ACME"} or {"site": "acme", "company": "ACME"} for Lever'>
          <JsonEditor
            value={config}
            onChange={(v, valid) => {
              setConfig(v);
              setConfigValid(valid);
            }}
          />
        </Field>
        <Button onClick={create} disabled={!name || !effectiveAdapter || !configValid}>
          Create source
        </Button>
      </Card>

      <Card title="All sources">
        {sources.loading && <p>Loading...</p>}
        {sources.data && sources.data.length === 0 && <EmptyState>No sources yet.</EmptyState>}
        {sources.data && sources.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Adapter</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sources.data.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.name}</strong>
                    <div className="muted">{s.base_url}</div>
                  </td>
                  <td>
                    <code>{s.adapter_key}</code>
                  </td>
                  <td>
                    <Badge on={s.enabled} />
                  </td>
                  <td className="row-actions">
                    <Button variant="ghost" onClick={() => test(s.id)}>
                      Test scrape
                    </Button>
                    <Button variant="ghost" onClick={() => toggle(s.id, !s.enabled)}>
                      {s.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button variant="danger" onClick={() => remove(s.id)}>
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
