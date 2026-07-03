/** Pipeline stage badge for the applications view. */

import type { ApplicationPipelineStage } from "../types";

const LABELS: Record<ApplicationPipelineStage, string> = {
  queued: "Submitting",
  apply_failed: "Apply failed",
  awaiting_reply: "Awaiting reply",
  ghosted: "Ghosted",
  interview_pending: "Interview pending",
  rejected: "Rejected",
  closed: "Listing closed",
  archived: "Archived",
};

export function ApplicationStageBadge({ stage }: { stage: ApplicationPipelineStage }) {
  return <span className={`badge badge-pipeline badge-pipeline-${stage}`}>{LABELS[stage]}</span>;
}
