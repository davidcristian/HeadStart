import { PortalCategoryFilters } from "../../components/PortalCategoryFilters";
import { Banner, Button, Card, EmptyState, Field } from "../../components/ui";
import { MAX_PORTAL_SELECTION } from "../../lib/portals";
import type { Portal, PortalCategory } from "../../types";
import { PortalSelectCard } from "./PortalSelectCard";

type PortalsSearchCardProps = {
  category: PortalCategory | "";
  setCategory: (category: PortalCategory | "") => void;
  categories: PortalCategory[];
  keywords: string;
  setKeywords: (value: string) => void;
  location: string;
  setLocation: (value: string) => void;
  workplace: "" | "remote" | "hybrid" | "onsite";
  setWorkplace: (value: "" | "remote" | "hybrid" | "onsite") => void;
  catalogItems: Portal[];
  selectedIds: Set<string>;
  selectPortals: (ids: Set<string>) => void;
  togglePortal: (portalId: string) => void;
  portalsPending: boolean;
  portalsError: boolean;
  onSearch: () => void;
  searchPending: boolean;
};

export function PortalsSearchCard({
  category,
  setCategory,
  categories,
  keywords,
  setKeywords,
  location,
  setLocation,
  workplace,
  setWorkplace,
  catalogItems,
  selectedIds,
  selectPortals,
  togglePortal,
  portalsPending,
  portalsError,
  onSearch,
  searchPending,
}: PortalsSearchCardProps) {
  const atCap = selectedIds.size >= MAX_PORTAL_SELECTION;

  return (
    <Card title="Search">
      <div className="portal-catalog-toolbar">
        <PortalCategoryFilters category={category} categories={categories} onChange={setCategory} />
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
              onChange={(e) => setWorkplace(e.target.value as "" | "remote" | "hybrid" | "onsite")}
            >
              <option value="">Any</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </Field>
        </div>
      </div>

      {portalsPending && <p>Loading companies...</p>}
      {portalsError && <Banner kind="error">Could not load the company catalog.</Banner>}
      {catalogItems.length > 0 && (
        <div className="portal-select-toolbar">
          <span className="muted">
            {selectedIds.size} of {catalogItems.length} selected
            {catalogItems.length > MAX_PORTAL_SELECTION
              ? ` (max ${MAX_PORTAL_SELECTION} per search)`
              : ""}
          </span>
          <Button
            variant="ghost"
            onClick={() => selectPortals(new Set(catalogItems.map((p) => p.id)))}
          >
            Select all
          </Button>
          <Button variant="ghost" onClick={() => selectPortals(new Set())}>
            Clear
          </Button>
        </div>
      )}
      {catalogItems.length > 0 && (
        <ul className="portal-grid portal-select-grid">
          {catalogItems.map((portal) => {
            const checked = selectedIds.has(portal.id);
            return (
              <PortalSelectCard
                key={portal.id}
                portal={portal}
                checked={checked}
                disabled={!checked && atCap}
                onToggle={() => togglePortal(portal.id)}
              />
            );
          })}
        </ul>
      )}
      {!portalsPending && catalogItems.length === 0 && (
        <EmptyState>No companies available on your plan for this filter.</EmptyState>
      )}

      <div className="portal-search-actions">
        <Button onClick={() => void onSearch()} disabled={searchPending}>
          {searchPending ? "Searching..." : "Search jobs"}
        </Button>
      </div>
    </Card>
  );
}
