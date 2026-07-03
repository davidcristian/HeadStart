import type { JobStatus } from "./job";

export type ApplicationPipelineStage =
  | "queued"
  | "apply_failed"
  | "awaiting_reply"
  | "ghosted"
  | "interview_pending"
  | "rejected"
  | "closed"
  | "archived";

export interface ApplicationArtifactMeta {
  id: number;
  artifact_type: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  content_sha256: string;
  created_at: string;
}

export interface ApplicationAttemptSummary {
  id: number;
  status: string;
  error: string | null;
  external_application_id: string | null;
  tailored_resume_artifact: ApplicationArtifactMeta | null;
  created_at: string;
}

export interface ReplyDraftSummary {
  id: number;
  classification_id: number;
  subject: string;
  body_text: string;
  provider: string;
  created_at: string;
}

export interface ReplyDraftResult extends ReplyDraftSummary {
  seen_job_id: number | null;
  message_uid: number;
  fallback: boolean;
  status: string;
  notes: string;
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
  ghost_recovered_at: string | null;
  interview_pending_at: string | null;
  recruiter_rejection_at: string | null;
  latest_attempt: ApplicationAttemptSummary | null;
  attempts: ApplicationAttemptSummary[];
  latest_reply_draft: ReplyDraftSummary | null;
  latest_draftable_classification_id: number | null;
}
