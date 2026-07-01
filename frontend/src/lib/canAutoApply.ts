/** Whether a job's source adapter supports auto-apply in the UI. */

import type { Job, Search, Source } from "../types";

export function canAutoApply(
  job: Job,
  searches: Search[],
  sources: Source[],
  appliers: string[],
): boolean {
  if (job.status === "applied" || job.status === "closed" || job.status === "archived") {
    return false;
  }
  const search = searches.find((item) => item.id === job.search_id);
  if (!search) return false;
  const source = sources.find((item) => item.id === search.source_id);
  if (!source) return false;
  return appliers.includes(source.adapter_key);
}
