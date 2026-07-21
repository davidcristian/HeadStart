/** Create and manage searches: the core "notify me about X" configuration. */

import { useState } from "react";
import { SearchHealthBadge, SearchHealthDetails, SearchLastRun } from "../components/SearchHealth";
import { SearchFiltersForm } from "../components/SearchFiltersForm";
import { JsonEditor } from "../components/JsonEditor";
import { PlanUsageHint } from "../components/PlanUsageHint";
import { Badge, Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useMeta, useSearches, useSources, useTargets } from "../hooks/queries";
import {
  useCreateSearch,
  useDeleteSearch,
  useRunSearch,
  useUpdateSearch,
} from "../hooks/mutations";
import { EMPTY_SEARCH_FILTERS, formToFilters, type SearchFilterForm } from "../lib/searchFilters";
import { canAddResource } from "../lib/plan";
import type { Json } from "../types";

export function SearchesPage() {
  const searches = useSearches();
  const sources = useSources();
  const targets = useTargets();
  const meta = useMeta();
  const createSearch = useCreateSearch();
  const updateSearch = useUpdateSearch();
  const deleteSearch = useDeleteSearch();
  const runSearch = useRunSearch();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const [name, setName] = useState("");
  const [sourceId, setSourceId] = useState<number | "">("");
  const [targetId, setTargetId] = useState<number | "">("");
  const [queryUrl, setQueryUrl] = useState("");
  const [interval, setInterval] = useState(900);
  const [notificationMode, setNotificationMode] = useState<"immediate" | "digest">("immediate");
  const [digestInterval, setDigestInterval] = useState(3600);
  const [filterForm, setFilterForm] = useState<SearchFilterForm>(EMPTY_SEARCH_FILTERS);
  const [config, setConfig] = useState<Json>({});
  const [configValid, setConfigValid] = useState(true);

  const sourceName = (id: number) => sources.data?.find((s) => s.id === id)?.name ?? `#${id}`;
  const targetName = (id: number | null) =>
    id == null ? "-" : (targets.data?.find((t) => t.id === id)?.name ?? `#${id}`);
  const plan = meta.data?.plan;
  const canCreate = plan ? canAddResource(plan, "searches") : true;
  const digestAllowed = plan?.features.digest_mode ?? true;

  async function create() {
    setError(undefined);
    try {
      await createSearch.mutateAsync({
        name,
        source_id: Number(sourceId),
        target_id: targetId === "" ? null : Number(targetId),
        query_url: queryUrl,
        filters: formToFilters(filterForm),
        config,
        interval_seconds: interval,
        notification_mode: notificationMode,
        digest_interval_seconds: digestInterval,
        enabled: true,
      });
      setName("");
      setQueryUrl("");
      setFilterForm(EMPTY_SEARCH_FILTERS);
      setConfig({});
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggle(id: number, enabled: boolean) {
    await updateSearch.mutateAsync({ id, data: { enabled } });
  }

  async function runNow(id: number) {
    setError(undefined);
    setNotice(undefined);
    try {
      const result = await runSearch.mutateAsync(id);
      if (result.error) {
        setError(`Run failed: ${result.error}`);
      } else {
        setNotice(
          `Found ${result.found}, ${result.new} new, ${result.notified} notified` +
            (result.queued ? `, ${result.queued} queued for digest` : "") +
            (result.filtered ? `, ${result.filtered} filtered out` : "") +
            (result.skipped ? `, ${result.skipped} skipped (already notified)` : "") +
            (result.closed ? `, ${result.closed} marked closed` : "") +
            (result.failed ? `, ${result.failed} delivery failure(s)` : "") +
            ".",
        );
      }
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: number) {
    await deleteSearch.mutateAsync(id);
  }

  return (
    <>
      <h1>Searches</h1>

      <Card title="Create a search">
        {plan && <PlanUsageHint plan={plan} resource="searches" />}
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
          <Field
            label="Notification mode"
            hint={digestAllowed ? undefined : "Digest mode requires Starter or above."}
          >
            <select
              value={notificationMode}
              onChange={(e) => setNotificationMode(e.target.value as "immediate" | "digest")}
            >
              <option value="immediate">Immediate (one alert per job)</option>
              <option value="digest" disabled={!digestAllowed}>
                Digest (batched summary){digestAllowed ? "" : " requires Starter+"}
              </option>
            </select>
          </Field>
          {notificationMode === "digest" && (
            <Field label="Digest interval (seconds)" hint="How often to send a batched summary.">
              <input
                type="number"
                min={60}
                value={digestInterval}
                onChange={(e) => setDigestInterval(Number(e.target.value))}
              />
            </Field>
          )}
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
        <SearchFiltersForm value={filterForm} onChange={setFilterForm} />
        <Field label="Config overrides (JSON)" hint="Per-search scraper config.">
          <JsonEditor
            value={config}
            onChange={(v, valid) => {
              setConfig(v);
              setConfigValid(valid);
            }}
          />
        </Field>
        <Button onClick={create} disabled={!name || sourceId === "" || !configValid || !canCreate}>
          Create search
        </Button>
      </Card>

      <Card title="All searches">
        {searches.isPending && <p>Loading...</p>}
        {searches.data && searches.data.length === 0 && (
          <EmptyState>No searches yet. Create one above.</EmptyState>
        )}
        {searches.data && searches.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Source</th>
                <th>Target</th>
                <th>Every</th>
                <th>Delivery</th>
                <th>Last run</th>
                <th>Health</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {searches.data.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.name}</strong>
                    <SearchHealthDetails search={s} />
                  </td>
                  <td>{sourceName(s.source_id)}</td>
                  <td>{targetName(s.target_id)}</td>
                  <td>{s.interval_seconds}s</td>
                  <td>
                    {s.notification_mode === "digest"
                      ? `Digest every ${s.digest_interval_seconds}s`
                      : "Immediate"}
                  </td>
                  <td>
                    <SearchLastRun at={s.last_run_at} />
                  </td>
                  <td>
                    <SearchHealthBadge search={s} />
                  </td>
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
