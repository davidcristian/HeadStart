import type { PortalCategory } from "../types";

/** Matches backend `portal_ids` max_length on search/subscribe schemas. */
export const MAX_PORTAL_SELECTION = 30;

export const PORTAL_CATEGORY_LABELS: Record<PortalCategory, string> = {
  big_tech: "Big tech",
  unicorn: "Unicorns",
  ai: "AI",
};

/** Keep at most `limit` portal ids (catalog order), for the API cap. */
export function capPortalIds(ids: Iterable<string>, limit = MAX_PORTAL_SELECTION): Set<string> {
  const capped = new Set<string>();
  for (const id of ids) {
    if (capped.size >= limit) break;
    capped.add(id);
  }
  return capped;
}
