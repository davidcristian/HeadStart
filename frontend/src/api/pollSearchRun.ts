/** Poll a queued manual search run until it reaches a terminal status. */

import { api } from "./index";
import type { SearchRunResult } from "../types";

const TERMINAL_STATUSES = new Set(["ready", "failed"]);
const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export async function pollSearchRun(runId: number): Promise<SearchRunResult> {
  const started = Date.now();
  while (Date.now() - started < POLL_TIMEOUT_MS) {
    const run = await api.getSearchRun(runId);
    if (TERMINAL_STATUSES.has(run.status)) {
      return run;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error("Search run is still processing. Try again in a moment.");
}
