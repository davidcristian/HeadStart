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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
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
    onSuccess: (result, variables) => {
      invalidate(qc, queryKeys.applicationLogs);
      // A live apply moves the job into the pipeline (queued / apply_failed / …), so
      // refetch every stage-filtered applications cache. Dry-run previews don't.
      if (!variables.dry_run) {
        invalidate(qc, ["applications"]);
      }
      if (result.status === "submitted") {
        qc.invalidateQueries({ queryKey: ["jobs"] });
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
