import type { JobStatus } from "./job";

export type ApplicationPipelineStage =
  | "queued"
  | "apply_failed"
  | "awaiting_reply"
  | "ghosted"
  | "closed"
  | "archived";

export interface ApplicationAttemptSummary {
  id: number;
  status: string;
  error: string | null;
  external_application_id: string | null;
  created_at: string;
}

export interface ApplicationPipelineItem {
  job_id: number;
  search_id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  job_status: JobStatus;
  pipeline_stage: ApplicationPipelineStage;
  applied_at: string | null;
  ghosted_at: string | null;
  latest_attempt: ApplicationAttemptSummary | null;
  attempts: ApplicationAttemptSummary[];
}
