/** State and handlers for the cross-portal company search page. */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMeta, usePortals, useTargets } from "../../hooks/queries";
import { useSearchPortals, useSubscribePortals } from "../../hooks/mutations";
import type { PortalCategory, PortalSearchResult } from "../../types";

export function usePortalsPage() {
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

  // Select all portals when the available catalog changes (first load or a new
  // category), but keep the user's manual selection across plain refetches that
  // return the same set of portals.
  const catalogKey = useMemo(
    () => catalogItems.map((portal) => portal.id).sort().join("\n"),
    [catalogItems],
  );
  const initializedKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (catalogItems.length === 0) return;
    if (initializedKeyRef.current === catalogKey) return;
    initializedKeyRef.current = catalogKey;
    setSelectedIds(new Set(catalogItems.map((portal) => portal.id)));
  }, [catalogItems, catalogKey]);

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

  return {
    plan: meta.data?.plan.plan ?? "free",
    portalSearchAllowed,
    error,
    notice,
    category,
    setCategory,
    categories: portals.data?.categories ?? [],
    keywords,
    setKeywords,
    location,
    setLocation,
    workplace,
    setWorkplace,
    selectedIds,
    setSelectedIds,
    catalogItems,
    togglePortal,
    portals,
    runSearch,
    searchPortals,
    results,
    targets: targets.data ?? [],
    targetId,
    setTargetId,
    interval,
    setInterval,
    createAlerts,
    subscribePortals,
  };
}
