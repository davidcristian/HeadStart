/** Search curated FAANG-adjacent and unicorn employer portals in one place (Pro+). */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useMeta, usePortals, useTargets } from "../hooks/queries";
import { useSearchPortals, useSubscribePortals } from "../hooks/mutations";
import { planLabel } from "../lib/plan";
import type { Portal, PortalCategory, PortalSearchResult } from "../types";

const CATEGORY_LABELS: Record<PortalCategory, string> = {
  big_tech: "Big tech",
  unicorn: "Unicorns",
  ai: "AI",
};

export function PortalsPage() {
  const meta = useMeta();
  const targets = useTargets();
  const portalSearchAllowed = meta.data?.plan.features.portal_search ?? false;
  const [category, setCategory] = useState<PortalCategory | "">("");
  const portals = usePortals(category || undefined);
  const searchPortals = useSearchPortals();
  const subscribePortals = useSubscribePortals();

  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const [workplace, setWorkplace] = useState<"" | "remote" | "hybrid" | "onsite">("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [targetId, setTargetId] = useState<number | "">("");
  const [interval, setInterval] = useState(900);
  const [results, setResults] = useState<PortalSearchResult | null>(null);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const catalogItems = useMemo(() => {
    const items = portals.data?.items ?? [];
    return items.filter((portal) => portal.allowed_on_plan);
  }, [portals.data?.items]);

  useEffect(() => {
    if (catalogItems.length === 0) return;
    setSelectedIds(new Set(catalogItems.map((portal) => portal.id)));
  }, [catalogItems]);

  function togglePortal(portalId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(portalId)) next.delete(portalId);
      else next.add(portalId);
      return next;
    });
  }

  function searchPayload() {
    const portal_ids = [...selectedIds];
    return {
      keywords: keywords.trim(),
      ...(category ? { category } : {}),
      ...(portal_ids.length > 0 ? { portal_ids } : {}),
      ...(location.trim() ? { location: location.trim() } : {}),
      ...(workplace ? { workplace } : {}),
    };
  }

  async function runSearch() {
    setError(undefined);
    setNotice(undefined);
    if (!keywords.trim()) {
      setError("Enter keywords to search across company portals.");
      return;
    }
    if (selectedIds.size === 0) {
      setError("Select at least one company portal.");
      return;
    }
    try {
      const data = await searchPortals.mutateAsync(searchPayload());
      setResults(data);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createAlerts() {
    setError(undefined);
    setNotice(undefined);
    if (!keywords.trim()) {
      setError("Enter keywords before creating alerts.");
      return;
    }
    if (selectedIds.size === 0) {
      setError("Select at least one company portal.");
      return;
    }
    if (targetId === "") {
      setError("Pick a notification target for new alerts.");
      return;
    }
    try {
      const data = await subscribePortals.mutateAsync({
        ...searchPayload(),
        portal_ids: [...selectedIds],
        target_id: Number(targetId),
        interval_seconds: interval,
      });
      const parts = [
        data.searches_created > 0
          ? `Created ${data.searches_created} search${data.searches_created === 1 ? "" : "es"}`
          : null,
        data.sources_created > 0
          ? `added ${data.sources_created} source${data.sources_created === 1 ? "" : "s"}`
          : null,
        data.skipped_portal_ids.length > 0
          ? `skipped ${data.skipped_portal_ids.length} duplicate${data.skipped_portal_ids.length === 1 ? "" : "s"}`
          : null,
      ].filter(Boolean);
      setNotice(parts.join("; ") + (data.message ? `. ${data.message}` : "."));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!portalSearchAllowed) {
    const plan = meta.data?.plan.plan ?? "free";
    return (
      <div className="page-stack">
        <h1>Company search</h1>
        <Banner kind="info">
          Search across curated FAANG-adjacent, unicorn, and AI employer portals in one place.
          Upgrade to Pro or Team to unlock cross-portal search and one-click alerts. You are on the{" "}
          {planLabel(plan)} plan.
        </Banner>
        <p>
          <Link to="/pricing">View pricing</Link> or browse individual companies on the{" "}
          <Link to="/app/sources">Sources</Link> page.
        </p>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <h1>Company search</h1>
      <p className="muted portal-page-intro">
        Search open roles across curated employer career sites, then subscribe to alerts without
        hand-configuring each board.
      </p>

      {error && <Banner kind="error">{error}</Banner>}
      {notice && <Banner kind="success">{notice}</Banner>}

      <Card title="Search">
        <div className="portal-catalog-toolbar">
          <div className="portal-category-tabs" role="tablist" aria-label="Portal categories">
            <button
              type="button"
              role="tab"
              className={category === "" ? "portal-tab active" : "portal-tab"}
              aria-selected={category === ""}
              onClick={() => setCategory("")}
            >
              All
            </button>
            {(portals.data?.categories ?? []).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                className={category === key ? "portal-tab active" : "portal-tab"}
                aria-selected={category === key}
                onClick={() => setCategory(key)}
              >
                {CATEGORY_LABELS[key]}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <Field label="Keywords" hint="Matched against job title, company, and location.">
              <input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="software engineer"
              />
            </Field>
            <Field label="Location contains">
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="remote, san francisco"
              />
            </Field>
            <Field label="Workplace">
              <select
                value={workplace}
                onChange={(e) =>
                  setWorkplace(e.target.value as "" | "remote" | "hybrid" | "onsite")
                }
              >
                <option value="">Any</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">On-site</option>
              </select>
            </Field>
          </div>
        </div>

        {portals.isPending && <p>Loading companies...</p>}
        {portals.isError && <Banner kind="error">Could not load the company catalog.</Banner>}
        {catalogItems.length > 0 && (
          <div className="portal-select-toolbar">
            <span className="muted">
              {selectedIds.size} of {catalogItems.length} selected
            </span>
            <Button
              variant="ghost"
              onClick={() => setSelectedIds(new Set(catalogItems.map((p) => p.id)))}
            >
              Select all
            </Button>
            <Button variant="ghost" onClick={() => setSelectedIds(new Set())}>
              Clear
            </Button>
          </div>
        )}
        {catalogItems.length > 0 && (
          <ul className="portal-grid portal-select-grid">
            {catalogItems.map((portal) => (
              <PortalSelectCard
                key={portal.id}
                portal={portal}
                checked={selectedIds.has(portal.id)}
                onToggle={() => togglePortal(portal.id)}
              />
            ))}
          </ul>
        )}
        {!portals.isPending && catalogItems.length === 0 && (
          <EmptyState>No companies available on your plan for this filter.</EmptyState>
        )}

        <div className="portal-search-actions">
          <Button onClick={() => void runSearch()} disabled={searchPortals.isPending}>
            {searchPortals.isPending ? "Searching..." : "Search jobs"}
          </Button>
        </div>
      </Card>

      {results && (
        <Card title={`Results (${results.items.length})`}>
          <p className="muted">
            Searched {results.portals_searched} portal{results.portals_searched === 1 ? "" : "s"}
            {results.portals_failed > 0
              ? `; ${results.portals_failed} failed (see errors below)`
              : ""}
            .
          </p>
          {results.errors.length > 0 && (
            <ul className="portal-search-errors">
              {results.errors.map((item) => (
                <li key={item.portal_id}>
                  <strong>{item.company_name}:</strong> {item.error}
                </li>
              ))}
            </ul>
          )}
          {results.items.length === 0 ? (
            <EmptyState>
              No matching jobs right now. Try broader keywords or more companies.
            </EmptyState>
          ) : (
            <ul className="portal-results-list">
              {results.items.map((job) => (
                <li key={`${job.portal_id}-${job.external_id}`} className="portal-result-row">
                  <div>
                    <strong>{job.title}</strong>
                    <div className="muted">
                      {job.company_name}
                      {job.location ? ` · ${job.location}` : ""}
                    </div>
                  </div>
                  {job.url ? (
                    <a href={job.url} target="_blank" rel="noreferrer">
                      View
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card title="Subscribe to alerts">
        <p className="muted">
          Creates a source (if needed) and a scheduled search per selected company with your keyword
          filters.
        </p>
        <div className="form-grid">
          <Field label="Notification target">
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">Select target</option>
              {(targets.data ?? []).map((target) => (
                <option key={target.id} value={target.id}>
                  {target.name} ({target.type})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Check interval (seconds)">
            <input
              type="number"
              min={60}
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
            />
          </Field>
        </div>
        {targets.data?.length === 0 && (
          <p className="muted">
            <Link to="/app/targets">Create a notification target</Link> first.
          </p>
        )}
        <Button onClick={() => void createAlerts()} disabled={subscribePortals.isPending}>
          {subscribePortals.isPending ? "Creating..." : "Create alerts"}
        </Button>
      </Card>
    </div>
  );
}

function PortalSelectCard({
  portal,
  checked,
  onToggle,
}: {
  portal: Portal;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <li className={`portal-card portal-select-card ${checked ? "selected" : ""}`}>
      <label className="portal-select-label">
        <input type="checkbox" checked={checked} onChange={onToggle} />
        <span>
          <strong>{portal.company_name}</strong>
          <span className="portal-card-meta">
            <span className="portal-chip">{CATEGORY_LABELS[portal.category]}</span>
            {portal.already_added && (
              <span className="portal-chip portal-chip-muted">Source added</span>
            )}
          </span>
        </span>
      </label>
    </li>
  );
}
