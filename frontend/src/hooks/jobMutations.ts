/** Job feed and auto-apply mutations. */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { queryKeys } from "./queries";
import { invalidate } from "./mutationUtils";

export function useUpdateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: "seen" | "applied" | "archived" }) =>
      api.updateJob(id, { status }),
    onSuccess: () => {
      // Status changes (applied/archived/seen) also drive pipeline stage on
      // /app/applications — keep both caches fresh (FRO-30).
      invalidate(qc, ["jobs"]);
      invalidate(qc, ["applications"]);
    },
  });
}

export function useApplyToJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      dry_run = false,
      cover_letter,
      tailored_resume_b64,
      tailored_resume_artifact_id,
    }: {
      id: number;
      dry_run?: boolean;
      cover_letter?: string | null;
      tailored_resume_b64?: string | null;
      tailored_resume_artifact_id?: number | null;
    }) =>
      api.applyToJob(id, {
        dry_run,
        cover_letter,
        tailored_resume_b64,
        tailored_resume_artifact_id,
      }),
    onSuccess: (_result, variables) => {
      invalidate(qc, queryKeys.applicationLogs);
      // A live apply moves the job into the pipeline (queued / apply_failed / …), so
      // refetch applications and jobs. Live enqueue returns status=queued (API-10);
      // do not gate jobs refresh on unreachable "submitted" (FRO-31 / XCT-27).
      // Dry-run previews don't.
      if (!variables.dry_run) {
        invalidate(qc, ["applications"]);
        invalidate(qc, ["jobs"]);
      }
    },
  });
}

export function useGenerateCoverLetter() {
  return useMutation({
    mutationFn: (jobId: number) => api.generateCoverLetter(jobId),
  });
}

export function useGenerateResume() {
  return useMutation({
    mutationFn: (jobId: number) => api.generateResume(jobId),
  });
}
