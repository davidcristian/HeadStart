import type { User } from "./auth";
import type { PromoRedemption } from "./billing";
import type { ApplicationLog, Job } from "./job";
import type { NotificationTarget } from "./target";
import type { Search } from "./search";
import type { Source } from "./source";
import type { CredentialExport } from "./credentials";

export interface ProfileLinks {
  linkedin: string;
  github: string;
  website: string;
}

export interface WorkExperienceEntry {
  job_title: string;
  company: string;
  location: string;
  start_month: number | null;
  start_year: number | null;
  end_month: number | null;
  end_year: number | null;
  is_current: boolean;
  description: string;
}

export interface EducationEntry {
  school: string;
  degree: string;
  field_of_study: string;
  start_year: number | null;
  end_year: number | null;
  gpa: string;
}

export interface LanguageEntry {
  language: string;
  proficiency: string;
  is_native: boolean;
}

export interface ProfileData {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  links: ProfileLinks;
  resume_text: string;
  cover_letter_template: string;
  answers: Record<string, string>;
  work_experience: WorkExperienceEntry[];
  education: EducationEntry[];
  skills: string[];
  languages: LanguageEntry[];
}

export interface ResumeFileMeta {
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface ResumeTemplateMeta {
  filename: string;
  size_bytes: number;
  format: "single" | "bundle";
  entrypoint: string | null;
  file_count: number | null;
}

export interface Profile extends ProfileData {
  exists: boolean;
  updated_at: string | null;
  resume_file: ResumeFileMeta | null;
  resume_template: ResumeTemplateMeta | null;
}

export interface ProfileFileExport {
  filename: string;
  content_type?: string | null;
  data_b64: string;
  format?: string | null;
  entrypoint?: string | null;
  file_count?: number | null;
}

export interface ApplicationArtifactExport {
  id: number;
  artifact_type: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  content_sha256: string;
  created_at: string;
  data_b64: string;
}

export interface DeliveryLogExport {
  id: number;
  seen_job_id: number;
  target_id: number | null;
  status: string;
  error: string | null;
  sent_at: string;
}

export interface MailboxCredentialExport {
  id: number;
  connector_type: string;
  enabled: boolean;
  created_at: string;
  config: Record<string, unknown>;
}

export interface InboxClassificationExport {
  id: number;
  seen_job_id: number | null;
  message_uid: number;
  message_id: string | null;
  label: string;
  confidence: number;
  reason: string;
  provider: string;
  fallback: boolean;
  subject: string;
  from_addr: string;
  payload: Record<string, unknown> | null;
  routed_to: string | null;
  routing_status: string | null;
  routing_error: string | null;
  created_at: string;
}

export interface InboxReplyDraftExport {
  id: number;
  inbox_classification_id: number;
  seen_job_id: number | null;
  message_uid: number;
  subject: string;
  body_text: string;
  provider: string;
  fallback: boolean;
  status: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface InboxPendingReplyExport {
  id: number;
  inbox_reply_draft_id: number;
  send_after: string;
  status: string;
  sent_at: string | null;
  error: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface InboxReplySendLogExport {
  id: number;
  inbox_reply_draft_id: number;
  inbox_pending_reply_id: number | null;
  outcome: string;
  reason: string;
  subject: string;
  body_excerpt: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface UserDataExport {
  exported_at: string;
  format_version: number;
  account: User;
  sources: Source[];
  searches: Search[];
  targets: NotificationTarget[];
  credentials: CredentialExport[];
  profile: Profile | null;
  resume_file: ProfileFileExport | null;
  resume_template: ProfileFileExport | null;
  jobs: Job[];
  applications: ApplicationLog[];
  artifacts: ApplicationArtifactExport[];
  deliveries: DeliveryLogExport[];
  mailbox: MailboxCredentialExport | null;
  inbox_classifications: InboxClassificationExport[];
  inbox_reply_drafts: InboxReplyDraftExport[];
  inbox_pending_replies: InboxPendingReplyExport[];
  inbox_reply_send_logs: InboxReplySendLogExport[];
  promo_redemptions: PromoRedemption[];
}
