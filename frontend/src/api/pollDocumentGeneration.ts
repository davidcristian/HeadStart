/** Poll a queued document generation until it reaches a terminal status. */

import { api } from "./index";
import type { DocumentGeneration } from "../types";

const TERMINAL_STATUSES = new Set(["ready", "failed"]);
const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export async function pollDocumentGeneration(generationId: number): Promise<DocumentGeneration> {
  const started = Date.now();
  while (Date.now() - started < POLL_TIMEOUT_MS) {
    const generation = await api.getDocumentGeneration(generationId);
    if (TERMINAL_STATUSES.has(generation.status)) {
      return generation;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error("Document generation is still processing. Try again in a moment.");
}
