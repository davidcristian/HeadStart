/** Static API response payloads for mockApi.ts (kept separate to stay under the LOC cap). */

import type { AdminStats, PortalList, User, UserDataExport } from "../types";

export const samplePortals: PortalList = {
  categories: ["big_tech", "unicorn", "ai"],
  items: [
    {
      id: "stripe",
      company_name: "Stripe",
      category: "unicorn",
      adapter_key: "greenhouse",
      base_url: "https://boards.greenhouse.io/stripe",
      default_config: { board_token: "stripe", company: "Stripe", portal_id: "stripe" },
      supports_auto_apply: true,
      allowed_on_plan: true,
      already_added: false,
    },
  ],
};

export const samplePortalSearchResult = {
  items: [
    {
      portal_id: "stripe",
      company_name: "Stripe",
      external_id: "1",
      title: "Software Engineer",
      location: "Remote",
      url: "https://example.com/jobs/1",
    },
  ],
  portals_searched: 1,
  portals_failed: 0,
  errors: [],
};

export const sampleSubscribePortalsResult = {
  sources_created: 1,
  searches_created: 1,
  search_ids: [42],
  skipped_portal_ids: [] as string[],
  message: null as string | null,
};

export const sampleDetectSource = {
  adapter_key: "greenhouse",
  suggested_name: "ACME Careers",
  base_url: "https://boards.greenhouse.io/acme",
  default_config: { board_token: "acme" },
  query_url: "https://boards.greenhouse.io/acme",
};

export const sampleTeamUser: User = {
  id: 1,
  email: "admin@example.com",
  is_admin: true,
  is_active: true,
  plan: "pro",
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

export const sampleUserDataExport: UserDataExport = {
  exported_at: "2026-06-28T12:00:00Z",
  format_version: 2,
  account: {
    id: 1,
    email: "admin@example.com",
    is_admin: true,
    is_active: true,
    plan: "pro",
    onboarding_completed_at: "2026-06-28T00:00:00Z",
    email_verified_at: "2026-06-28T00:00:00Z",
    created_at: "2026-06-28T00:00:00Z",
  },
  sources: [],
  searches: [],
  targets: [],
  credentials: [],
  profile: null,
  resume_file: null,
  resume_template: null,
  jobs: [],
  applications: [],
  artifacts: [],
  deliveries: [],
  mailbox: null,
  inbox_classifications: [],
  inbox_reply_drafts: [],
  inbox_pending_replies: [],
  inbox_reply_send_logs: [],
  promo_redemptions: [],
};

export const emptyAdminStats: AdminStats = {
  users_total: 0,
  users_active: 0,
  searches_total: 0,
  searches_enabled: 0,
  searches_with_error: 0,
  sources_total: 0,
  seen_jobs_total: 0,
  deliveries_sent: 0,
  deliveries_failed: 0,
  recent_errors: [],
};

export const sampleBillingStatus = {
  configured: false,
  plan: "free" as const,
  subscription_status: null,
  has_stripe_subscription: false,
  can_checkout: false,
  can_manage: false,
  trial_days: 14,
};

export const sampleRunSearchResult = {
  id: 1,
  search_id: 20,
  status: "ready" as const,
  found: 3,
  new: 1,
  notified: 1,
  failed: 0,
  skipped: 0,
  filtered: 0,
  queued: 0,
  closed: 0,
  error: null,
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:00:00Z",
};

export const sampleApplyJobResult = {
  status: "dry_run" as const,
  error: null,
  payload: { email: "ada@example.com", cover_letter_text: "Dear ACME team" },
  external_application_id: null,
  job: null,
  application_log_id: null,
};

export const sampleFeedUrl = {
  url: "http://localhost:8000/api/v1/feed/rss?token=test-token",
  token: "test-token",
};

export const sampleRotatedFeedUrl = {
  url: "http://localhost:8000/api/v1/feed/rss?token=rotated-token",
  token: "rotated-token",
};

export const sampleTestSourceResult = {
  ok: true,
  found: 2,
  sample: [{ external_id: "1", title: "Engineer", company: "ACME", location: "", url: "" }],
  error: null,
};

export function newSourceRecord(data: unknown) {
  return {
    id: 99,
    name: "New source",
    adapter_key: "greenhouse",
    base_url: "",
    default_config: {},
    enabled: true,
    auto_apply_enabled: false,
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  };
}

export function updatedSourceRecord(data: unknown) {
  return {
    id: 1,
    name: "ACME Careers",
    adapter_key: "greenhouse",
    base_url: "https://boards.greenhouse.io/acme",
    default_config: {},
    enabled: true,
    auto_apply_enabled: false,
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  };
}

export function newSearchRecord(data: unknown) {
  return {
    id: 99,
    name: "New search",
    source_id: 1,
    target_id: null,
    query_url: "",
    filters: {},
    config: {},
    interval_seconds: 900,
    notification_mode: "immediate" as const,
    digest_interval_seconds: 3600,
    enabled: true,
    last_run_at: null,
    last_digest_at: null,
    last_error: null,
    next_run_at: "2026-06-28T12:15:00Z",
    created_at: "2026-06-28T00:00:00Z",
    recent_delivery_failures: [],
    ...(data as object),
  };
}

export function updatedSearchRecord(data: unknown) {
  return {
    id: 20,
    name: "Google SWE",
    source_id: 1,
    target_id: 10,
    query_url: "https://example.test/jobs",
    filters: {},
    config: {},
    interval_seconds: 900,
    notification_mode: "immediate" as const,
    digest_interval_seconds: 3600,
    enabled: true,
    last_run_at: "2026-06-28T12:00:00Z",
    last_digest_at: null,
    last_error: null,
    next_run_at: "2026-06-28T12:15:00Z",
    created_at: "2026-06-28T00:00:00Z",
    recent_delivery_failures: [],
    ...(data as object),
  };
}

export function newTargetRecord(data: unknown) {
  return {
    id: 99,
    name: "New target",
    type: "ntfy",
    config: {},
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  };
}

export function newPromoCodeRecord(data: unknown) {
  return {
    id: 1,
    redemption_count: 0,
    active: true,
    one_per_user: true,
    eligible_plans: null,
    stripe_coupon_id: null,
    stripe_promotion_code_id: null,
    expires_at: null,
    created_at: "2026-06-28T00:00:00Z",
    plan_target: null,
    max_redemptions: null,
    ...(data as object),
  };
}

export function updatedPromoCodeRecord(id: number, data: unknown) {
  return {
    id,
    code: "TEST",
    promo_type: "percent_off" as const,
    value_int: 20,
    plan_target: null,
    max_redemptions: null,
    redemption_count: 0,
    expires_at: null,
    active: true,
    one_per_user: true,
    eligible_plans: null,
    stripe_coupon_id: null,
    stripe_promotion_code_id: null,
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  };
}
