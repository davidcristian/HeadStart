/** Create and manage searches: the core "notify me about X" configuration. */

import { useState } from "react";
import { api } from "../api";
import { JsonEditor } from "../components/JsonEditor";
import { Badge, Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import type { Json } from "../types";

export function SearchesPage() {
  const searches = useAsync(() => api.listSearches(), []);
  const sources = useAsync(() => api.listSources(), []);
  const targets = useAsync(() => api.listTargets(), []);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const [name, setName] = useState("");
  const [sourceId, setSourceId] = useState<number | "">("");
  const [targetId, setTargetId] = useState<number | "">("");
  const [queryUrl, setQueryUrl] = useState("");
  const [interval, setInterval] = useState(900);
  const [filters, setFilters] = useState<Json>({});
  const [config, setConfig] = useState<Json>({});
  const [jsonValid, setJsonValid] = useState(true);

  const sourceName = (id: number) => sources.data?.find((s) => s.id === id)?.name ?? `#${id}`;
  const targetName = (id: number | null) =>
    id == null ? "-" : (targets.data?.find((t) => t.id === id)?.name ?? `#${id}`);

  async function create() {
    setError(undefined);
    if (sourceId === "") {
      setError("Pick a source first (create one on the Sources page).");
      return;
    }
    try {
      await api.createSearch({
        name,
        source_id: Number(sourceId),
        target_id: targetId === "" ? null : Number(targetId),
        query_url: queryUrl,
        filters,
        config,
        interval_seconds: interval,
        enabled: true,
      });
      setName("");
      setQueryUrl("");
      setFilters({});
      setConfig({});
      searches.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggle(id: number, enabled: boolean) {
    await api.updateSearch(id, { enabled });
    searches.reload();
  }

  async function runNow(id: number) {
    setNotice(undefined);
    await api.runSearch(id);
    setNotice("Search queued; it will run on the next scheduler tick.");
  }

  async function remove(id: number) {
    await api.deleteSearch(id);
    searches.reload();
  }

  return (
    <>
      <h1>Searches</h1>

      <Card title="Create a search">
        {error && <Banner kind="error">{error}</Banner>}
        {notice && <Banner kind="info">{notice}</Banner>}
        <div className="form-grid">
          <Field label="Name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Google SWE Amsterdam"
            />
          </Field>
          <Field label="Source">
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">- choose -</option>
              {sources.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.adapter_key})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Notify via">
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">- none -</option>
              {targets.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Poll interval (seconds)">
            <input
              type="number"
              min={10}
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
            />
          </Field>
        </div>
        <Field
          label="Query URL"
          hint="The site's search/endpoint URL (optional for some adapters)."
        >
          <input
            value={queryUrl}
            onChange={(e) => setQueryUrl(e.target.value)}
            placeholder="https://..."
          />
        </Field>
        <div className="form-grid">
          <Field label="Filters (JSON)" hint='e.g. {"keywords": "engineer"}'>
            <JsonEditor
              value={filters}
              onChange={(v, valid) => {
                setFilters(v);
                setJsonValid(valid);
              }}
            />
          </Field>
          <Field label="Config overrides (JSON)" hint="Per-search scraper config.">
            <JsonEditor
              value={config}
              onChange={(v, valid) => {
                setConfig(v);
                setJsonValid(valid);
              }}
            />
          </Field>
        </div>
        <Button onClick={create} disabled={!name || sourceId === "" || !jsonValid}>
          Create search
        </Button>
      </Card>

      <Card title="All searches">
        {searches.loading && <p>Loading...</p>}
        {searches.data && searches.data.length === 0 && (
          <EmptyState>No searches yet. Create one above.</EmptyState>
        )}
        {searches.data && searches.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Source</th>
                <th>Notify</th>
                <th>Every</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {searches.data.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.name}</strong>
                  </td>
                  <td>{sourceName(s.source_id)}</td>
                  <td>{targetName(s.target_id)}</td>
                  <td>{s.interval_seconds}s</td>
                  <td>
                    <Badge on={s.enabled} />
                  </td>
                  <td className="row-actions">
                    <Button variant="ghost" onClick={() => runNow(s.id)}>
                      Run now
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
