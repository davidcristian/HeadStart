/** Browse curated employer portals and add them as sources in one click. */

import { useMemo, useState } from "react";
import { Banner, Button, Card, EmptyState, Field } from "../../components/ui";
import { useMeta, usePortals } from "../../hooks/queries";
import { useCreateSource } from "../../hooks/mutations";
import { canAddResource } from "../../lib/plan";
import type { Portal, PortalCategory } from "../../types";

const CATEGORY_LABELS: Record<PortalCategory, string> = {
  big_tech: "Big tech",
  unicorn: "Unicorns",
  ai: "AI",
};

type PortalCatalogProps = {
  onAdded?: (companyName: string) => void;
  onError?: (message: string) => void;
};

export function PortalCatalog({ onAdded, onError }: PortalCatalogProps) {
  const meta = useMeta();
  const createSource = useCreateSource();
  const [category, setCategory] = useState<PortalCategory | "">("");
  const [search, setSearch] = useState("");
  const [addingId, setAddingId] = useState<string | null>(null);

  const portals = usePortals(category || undefined, search.trim() || undefined);
  const plan = meta.data?.plan;
  const canCreate = plan ? canAddResource(plan, "sources") : true;

  const items = useMemo(() => portals.data?.items ?? [], [portals.data?.items]);

  async function addPortal(portal: Portal) {
    setAddingId(portal.id);
    try {
      await createSource.mutateAsync({
        name: portal.company_name,
        adapter_key: portal.adapter_key,
        base_url: portal.base_url,
        default_config: portal.default_config,
        enabled: true,
      });
      onAdded?.(portal.company_name);
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setAddingId(null);
    }
  }

  function actionLabel(portal: Portal): string {
    if (portal.already_added) return "Added";
    if (!portal.allowed_on_plan) return "Pro required";
    if (!canCreate) return "At limit";
    return "Add source";
  }

  function actionDisabled(portal: Portal): boolean {
    return (
      portal.already_added ||
      !portal.allowed_on_plan ||
      !canCreate ||
      addingId !== null ||
      createSource.isPending
    );
  }

  return (
    <Card title="Browse companies">
      <p className="muted portal-catalog-intro">
        One-click setup for curated FAANG-adjacent, unicorn, and AI employer career portals. Each
        preset uses a verified public job-board API.
      </p>
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
        <Field label="Search">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Company name"
            aria-label="Search companies"
          />
        </Field>
      </div>

      {portals.isPending && <p>Loading companies...</p>}
      {portals.isError && <Banner kind="error">Could not load the company catalog.</Banner>}
      {!portals.isPending && items.length === 0 && (
        <EmptyState>No companies match your filters.</EmptyState>
      )}
      {items.length > 0 && (
        <ul className="portal-grid">
          {items.map((portal) => (
            <li key={portal.id} className="portal-card">
              <div className="portal-card-main">
                <strong>{portal.company_name}</strong>
                <div className="portal-card-meta">
                  <span className="portal-chip">{CATEGORY_LABELS[portal.category]}</span>
                  <code>{portal.adapter_key}</code>
                  {portal.supports_auto_apply && (
                    <span className="portal-chip portal-chip-muted">Auto-apply</span>
                  )}
                </div>
              </div>
              <Button
                variant={portal.already_added ? "ghost" : "primary"}
                disabled={actionDisabled(portal)}
                onClick={() => void addPortal(portal)}
              >
                {addingId === portal.id ? "Adding..." : actionLabel(portal)}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
