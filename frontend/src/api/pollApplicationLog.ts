/** Poll a queued application log until it reaches a terminal status. */

import { api } from "./index";
import type { ApplicationLog } from "../types";

const TERMINAL_STATUSES = new Set(["submitted", "failed", "dry_run"]);
const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export async function pollApplicationLog(logId: number): Promise<ApplicationLog> {
  const started = Date.now();
  while (Date.now() - started < POLL_TIMEOUT_MS) {
    const log = await api.getApplicationLog(logId);
    if (TERMINAL_STATUSES.has(log.status)) {
      return log;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error(
    "Application is still processing. Check Application profile history for the result.",
  );
}
