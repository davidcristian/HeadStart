export type JobStatus = "new" | "seen" | "applied" | "archived" | "closed";

export interface Job {
  id: number;
  search_id: number;
  external_id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  url: string;
  summary: string;
  status: JobStatus;
  first_seen_at: string;
  applied_at: string | null;
}

export interface JobApplyResult {
  status: string;
  error: string | null;
  payload: Record<string, unknown> | null;
  external_application_id: string | null;
  job: Job | null;
  application_log_id: number | null;
}

export interface JobCoverLetterResult {
  cover_letter: string;
  provider: string;
  fallback: boolean;
}

export interface JobResumeResult {
  filename: string;
  size_bytes: number;
  content_sha256: string;
  pdf_b64: string;
  provider: string;
  fallback: boolean;
}

export interface ApplicationLog {
  id: number;
  seen_job_id: number;
  job_title: string;
  job_company: string;
  job_url: string;
  status: string;
  dry_run: boolean;
  error: string | null;
  payload: Record<string, unknown> | null;
  external_application_id: string | null;
  created_at: string;
}
