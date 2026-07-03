/** Sample API payloads for frontend smoke tests. */

import type {
  AccountPlan,
  ApplicationPipelineItem,
  Job,
  Meta,
  NotificationTarget,
  Profile,
  Search,
  Source,
} from "../types";

export const sampleAccountPlan: AccountPlan = {
  plan: "pro",
  effective_plan: "pro",
  unlimited: true,
  show_ads: false,
  limits: { max_searches: 50, max_sources: 50, max_targets: 20 },
  usage: { searches: 0, sources: 0, targets: 0 },
  features: {
    digest_mode: true,
    ai_summaries: true,
    site_credentials: true,
    rss_feed: true,
    portal_search: true,
  },
  allowed_scrapers: [
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "indeed",
    "linkedin",
    "generic_html",
    "playwright",
  ],
  allowed_notifiers: ["discord", "email", "ntfy", "slack", "telegram", "webhook"],
};

export const sampleMeta: Meta = {
  scrapers: sampleAccountPlan.allowed_scrapers,
  notifiers: sampleAccountPlan.allowed_notifiers,
  appliers: ["greenhouse", "lever", "ashby"],
  plan: sampleAccountPlan,
  ads: { external_slot_url: null },
};

export const sampleSource: Source = {
  id: 1,
  name: "ACME Careers",
  adapter_key: "greenhouse",
  base_url: "https://boards.greenhouse.io/acme",
  default_config: { board_token: "acme" },
  enabled: true,
  auto_apply_enabled: false,
  created_at: "2026-06-28T00:00:00Z",
};

export const sampleTarget: NotificationTarget = {
  id: 10,
  name: "My phone",
  type: "ntfy",
  config: { server_url: "https://ntfy.sh", topic: "jobs", priority: "default" },
  created_at: "2026-06-28T00:00:00Z",
};

export const sampleSearch: Search = {
  id: 20,
  name: "Google SWE",
  source_id: sampleSource.id,
  target_id: sampleTarget.id,
  query_url: "https://example.test/jobs",
  filters: { keywords: "engineer" },
  config: {},
  interval_seconds: 900,
  notification_mode: "immediate",
  digest_interval_seconds: 3600,
  enabled: true,
  last_run_at: "2026-06-28T12:00:00Z",
  last_digest_at: null,
  last_error: null,
  next_run_at: "2026-06-28T12:15:00Z",
  created_at: "2026-06-28T00:00:00Z",
  recent_delivery_failures: [],
};

export const emptyProfile: Profile = {
  full_name: "",
  email: "",
  phone: "",
  location: "",
  links: { linkedin: "", github: "", website: "" },
  resume_text: "",
  cover_letter_template: "",
  answers: {},
  work_experience: [],
  education: [],
  skills: [],
  languages: [],
  exists: false,
  updated_at: null,
  resume_file: null,
  resume_template: null,
};

export const sampleProfile: Profile = {
  full_name: "Ada Lovelace",
  email: "ada@example.com",
  phone: "+1 555 0100",
  location: "London, UK",
  links: { linkedin: "", github: "https://github.com/ada", website: "" },
  resume_text: "Pioneering programmer.",
  cover_letter_template: "Dear {company} team, ...",
  answers: { work_authorization: "UK citizen" },
  work_experience: [],
  education: [],
  skills: ["Python"],
  languages: [{ language: "English", proficiency: "Native", is_native: true }],
  exists: true,
  updated_at: "2026-06-28T12:00:00Z",
  resume_file: null,
  resume_template: null,
};

export const sampleJob: Job = {
  id: 100,
  search_id: sampleSearch.id,
  external_id: "job-1",
  title: "Software Engineer",
  company: "ACME",
  location: "Remote",
  salary: "$150K – $180K",
  url: "https://example.test/jobs/1",
  summary: "Matches your search: mentions engineer; remote role.",
  status: "new",
  first_seen_at: "2026-06-28T12:00:00Z",
  applied_at: null,
};

export const sampleApplicationPipelineItem: ApplicationPipelineItem = {
  job_id: sampleJob.id,
  search_id: sampleSearch.id,
  title: sampleJob.title,
  company: sampleJob.company,
  location: sampleJob.location,
  url: sampleJob.url,
  job_status: "applied",
  pipeline_stage: "awaiting_reply",
  applied_at: "2026-06-28T13:00:00Z",
  ghosted_at: null,
  ghost_recovered_at: null,
  interview_pending_at: null,
  recruiter_rejection_at: null,
  latest_attempt: {
    id: 1,
    status: "submitted",
    error: null,
    external_application_id: "gh-123",
    tailored_resume_artifact: null,
    created_at: "2026-06-28T13:00:00Z",
  },
  attempts: [
    {
      id: 1,
      status: "submitted",
      error: null,
      external_application_id: "gh-123",
      tailored_resume_artifact: null,
      created_at: "2026-06-28T13:00:00Z",
    },
  ],
  latest_reply_draft: null,
  latest_draftable_classification_id: null,
};
