/** Types mirroring the backend Pydantic schemas (see backend/app/schemas). */

export type Json = Record<string, unknown>;

export interface Source {
  id: number;
  name: string;
  adapter_key: string;
  base_url: string;
  default_config: Json;
  enabled: boolean;
  created_at: string;
}

export type SourceCreate = Omit<Source, "id" | "created_at">;

export interface SourceDetectResult {
  adapter_key: string;
  suggested_name: string;
  base_url: string;
  default_config: Json;
  query_url: string;
}

export interface JobPostingPreview {
  external_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
}

export interface SourceTestResult {
  ok: boolean;
  found: number;
  sample: JobPostingPreview[];
  error: string | null;
}

export interface DeliveryFailure {
  job_title: string;
  job_url: string;
  error: string | null;
  sent_at: string;
}

export interface Search {
  id: number;
  name: string;
  source_id: number;
  target_id: number | null;
  query_url: string;
  filters: Json;
  config: Json;
  interval_seconds: number;
  notification_mode: "immediate" | "digest";
  digest_interval_seconds: number;
  enabled: boolean;
  last_run_at: string | null;
  last_digest_at: string | null;
  last_error: string | null;
  next_run_at: string;
  created_at: string;
  recent_delivery_failures: DeliveryFailure[];
}

export type SearchCreate = Pick<
  Search,
  | "name"
  | "source_id"
  | "target_id"
  | "query_url"
  | "filters"
  | "config"
  | "interval_seconds"
  | "notification_mode"
  | "digest_interval_seconds"
  | "enabled"
>;

export interface SearchRunResult {
  search_id: number;
  found: number;
  new: number;
  notified: number;
  failed: number;
  skipped: number;
  filtered: number;
  queued: number;
  closed: number;
  error: string | null;
}

export interface NotificationTarget {
  id: number;
  name: string;
  type: string;
  config: Json;
  created_at: string;
}

export type TargetCreate = Omit<NotificationTarget, "id" | "created_at">;

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
}

export interface FeedUrl {
  url: string;
  token: string;
}

export interface Meta {
  scrapers: string[];
  notifiers: string[];
  plan: AccountPlan;
}

export type PlanId = "free" | "pro" | "team";

export interface PlanLimits {
  max_searches: number;
  max_sources: number;
  max_targets: number;
}

export interface PlanUsage {
  searches: number;
  sources: number;
  targets: number;
}

export interface PlanFeatures {
  digest_mode: boolean;
  ai_summaries: boolean;
  site_credentials: boolean;
  rss_feed: boolean;
}

export interface AccountPlan {
  plan: PlanId;
  effective_plan: PlanId;
  unlimited: boolean;
  limits: PlanLimits;
  usage: PlanUsage;
  features: PlanFeatures;
  allowed_scrapers: string[];
  allowed_notifiers: string[];
}

export interface Health {
  status: string;
  version: string;
  environment: string;
}

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  plan: PlanId;
  onboarding_completed_at: string | null;
  created_at: string;
}

export type BillingPeriod = "monthly" | "annual";

export interface BillingStatus {
  configured: boolean;
  plan: PlanId;
  subscription_status: string | null;
  has_stripe_subscription: boolean;
  can_checkout: boolean;
  can_manage: boolean;
  trial_days: number;
}

export type AdminUser = User;

export interface AdminSearchError {
  search_id: number;
  search_name: string;
  user_email: string;
  last_error: string;
  last_run_at: string | null;
}

export interface AdminStats {
  users_total: number;
  users_active: number;
  searches_total: number;
  searches_enabled: number;
  searches_with_error: number;
  sources_total: number;
  seen_jobs_total: number;
  deliveries_sent: number;
  deliveries_failed: number;
  recent_errors: AdminSearchError[];
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

export interface SiteCredential {
  id: number;
  source_id: number;
  name: string;
  enabled: boolean;
  created_at: string;
  has_cookies: boolean;
  has_headers: boolean;
  has_session: boolean;
}

export interface CredentialCreate {
  source_id: number;
  name: string;
  enabled: boolean;
  cookies: Record<string, string>;
  headers: Record<string, string>;
  session: Record<string, string>;
}

export interface ProfileLinks {
  linkedin: string;
  github: string;
  website: string;
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
}

export interface Profile extends ProfileData {
  exists: boolean;
  updated_at: string | null;
}

export interface CredentialExport {
  id: number;
  source_id: number;
  name: string;
  enabled: boolean;
  created_at: string;
  cookies: Record<string, string>;
  headers: Record<string, string>;
  session: Record<string, string>;
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
  jobs: Job[];
}
