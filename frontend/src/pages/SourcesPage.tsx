/** Manage sources (job sites + which scraper handles them). */

import { useState } from "react";
import { JsonEditor } from "../components/JsonEditor";
import { PlanUsageHint } from "../components/PlanUsageHint";
import { Badge, Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useMeta, useSources } from "../hooks/queries";
import {
  useCreateSource,
  useDeleteSource,
  useTestSource,
  useUpdateSource,
} from "../hooks/mutations";
import { canAddResource } from "../lib/plan";
import { PortalCatalog } from "./sources/PortalCatalog";
import type { Json } from "../types";

export function SourcesPage() {
  const sources = useSources();
  const meta = useMeta();
  const createSource = useCreateSource();
  const updateSource = useUpdateSource();
  const deleteSource = useDeleteSource();
  const testSource = useTestSource();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const [name, setName] = useState("");
  const [adapter, setAdapter] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [config, setConfig] = useState<Json>({});
  const [configValid, setConfigValid] = useState(true);

  const adapters = meta.data?.scrapers ?? [];
  const appliers = meta.data?.appliers ?? [];
  const effectiveAdapter = adapter || adapters[0] || "";
  const plan = meta.data?.plan;
  const canCreate = plan ? canAddResource(plan, "sources") : true;

  async function create() {
    setError(undefined);
    try {
      await createSource.mutateAsync({
        name,
        adapter_key: effectiveAdapter,
        base_url: baseUrl,
        default_config: config,
        enabled: true,
      });
      setName("");
      setBaseUrl("");
      setConfig({});
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggleAutoApply(id: number, autoApplyEnabled: boolean) {
    await updateSource.mutateAsync({ id, data: { auto_apply_enabled: autoApplyEnabled } });
  }

  async function remove(id: number) {
    await deleteSource.mutateAsync(id);
  }

  async function toggle(id: number, enabled: boolean) {
    await updateSource.mutateAsync({ id, data: { enabled } });
  }

  async function test(id: number) {
    setError(undefined);
    setNotice(undefined);
    try {
      const result = await testSource.mutateAsync(id);
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

      <PortalCatalog
        onAdded={(name) => {
          setError(undefined);
          setNotice(`Added ${name} as a source.`);
        }}
        onError={setError}
      />

      <Card title="Add a source manually">
        {plan && <PlanUsageHint plan={plan} resource="sources" />}
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
        <Field
          label="Default config (JSON)"
          hint='e.g. {"board_token": "acme", "company": "ACME"} or {"site": "acme", "company": "ACME"} for Lever'
        >
          <JsonEditor
            value={config}
            onChange={(v, valid) => {
              setConfig(v);
              setConfigValid(valid);
            }}
          />
        </Field>
        <Button
          onClick={create}
          disabled={!name || !effectiveAdapter || !configValid || !canCreate}
        >
          Create source
        </Button>
      </Card>

      <Card title="All sources">
        {sources.isPending && <p>Loading...</p>}
        {sources.data && sources.data.length === 0 && <EmptyState>No sources yet.</EmptyState>}
        {sources.data && sources.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Adapter</th>
                <th>Status</th>
                <th>Auto-apply</th>
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
                  <td>
                    {appliers.includes(s.adapter_key) ? (
                      <label className="checkbox-inline">
                        <input
                          type="checkbox"
                          checked={s.auto_apply_enabled}
                          onChange={(e) => void toggleAutoApply(s.id, e.target.checked)}
                        />
                        <span>{s.auto_apply_enabled ? "Enabled" : "Off"}</span>
                      </label>
                    ) : (
                      <span className="muted">N/A</span>
                    )}
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
