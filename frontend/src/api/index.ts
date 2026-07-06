/** Typed API endpoints. One function per backend route. */

import type {
  AccessTokenResponse,
  AdminStats,
  AdminUser,
  DataRequestLog,
  CredentialCreate,
  Health,
  Job,
  JobApplyResult,
  DocumentGeneration,
  ApplicationLog,
  ApplicationPipelineItem,
  ApplicationPipelineStage,
  FeedUrl,
  Meta,
  NotificationTarget,
  PlanId,
  Profile,
  ProfileData,
  PortalList,
  PortalSearchRequest,
  PortalSearchResult,
  PortalSubscribeRequest,
  PortalSubscribeResult,
  SummaryPreferences,
  SummaryPreferencesUpdate,
  Search,
  SearchCreate,
  SearchRunResult,
  SiteCredential,
  Source,
  SourceCreate,
  SourceDetectResult,
  SourceTestResult,
  TargetCreate,
  User,
  UserDataExport,
  BillingStatus,
  BillingPeriod,
  PromoCode,
  PromoRedemption,
  PromoValidation,
  PromoType,
} from "../types";
import type { PaidPlanId } from "../lib/pricing";
import { inboxApi } from "./inbox";
import { request, requestBlob, requestForm } from "./client";

function buildJobQuery(searchId?: number, status?: string): string {
  const params = new URLSearchParams();
  if (searchId !== undefined) params.set("search_id", String(searchId));
  if (status) params.set("status", status);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export const api = {
  // meta
  health: () => request<Health>("/api/v1/health", { skipAuth: true }),
  meta: () => request<Meta>("/api/v1/meta"),

  // auth
  register: (email: string, password: string) =>
    request<User>("/api/v1/auth/register", {
      method: "POST",
      body: { email, password },
      skipAuth: true,
    }),
  login: (email: string, password: string) =>
    request<AccessTokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
      skipAuth: true,
    }),
  logout: () =>
    request<{ message: string }>("/api/v1/auth/logout", {
      method: "POST",
      skipAuth: true,
    }),
  forgotPassword: (email: string) =>
    request<{ message: string }>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: { email },
      skipAuth: true,
    }),
  resetPassword: (token: string, password: string) =>
    request<{ message: string }>("/api/v1/auth/reset-password", {
      method: "POST",
      body: { token, password },
      skipAuth: true,
    }),
  verifyEmail: (token: string) =>
    request<User>("/api/v1/auth/verify-email", {
      method: "POST",
      body: { token },
      skipAuth: true,
    }),
  resendVerificationEmail: () =>
    request<{ message: string }>("/api/v1/auth/resend-verification", {
      method: "POST",
    }),
  me: () => request<User>("/api/v1/auth/me"),
  completeOnboarding: () =>
    request<User>("/api/v1/auth/me/complete-onboarding", { method: "POST" }),
  exportMyData: () => request<UserDataExport>("/api/v1/auth/me/export"),
  deleteAccount: (password: string) =>
    request<void>("/api/v1/auth/me", { method: "DELETE", body: { password } }),

  // billing
  billingStatus: () => request<BillingStatus>("/api/v1/billing/status"),
  validatePromoCode: (code: string) =>
    request<PromoValidation>("/api/v1/billing/promo/validate", {
      method: "POST",
      body: { code },
    }),
  createCheckout: (
    plan: PaidPlanId = "pro",
    billingPeriod: BillingPeriod = "monthly",
    promoCode?: string,
  ) =>
    request<{ url: string }>("/api/v1/billing/checkout", {
      method: "POST",
      body: {
        plan,
        billing_period: billingPeriod,
        ...(promoCode ? { promo_code: promoCode } : {}),
      },
    }),
  createBillingPortal: () =>
    request<{ url: string }>("/api/v1/billing/portal", { method: "POST", body: {} }),

  // admin
  listAdminUsers: () => request<AdminUser[]>("/api/v1/admin/users"),
  updateAdminUser: (
    id: number,
    data: Partial<Pick<AdminUser, "is_active" | "is_admin" | "plan">>,
  ) => request<AdminUser>(`/api/v1/admin/users/${id}`, { method: "PATCH", body: data }),
  getAdminStats: () => request<AdminStats>("/api/v1/admin/stats"),
  listAdminDataRequests: (limit = 100) =>
    request<DataRequestLog[]>(`/api/v1/admin/data-requests?limit=${limit}`),

  listAdminPromoCodes: () => request<PromoCode[]>("/api/v1/admin/promo-codes"),
  createAdminPromoCode: (data: {
    code: string;
    promo_type: PromoType;
    value_int: number;
    plan_target?: PlanId | null;
    max_redemptions?: number | null;
    expires_at?: string | null;
    one_per_user?: boolean;
    eligible_plans?: PlanId[] | null;
  }) =>
    request<PromoCode>("/api/v1/admin/promo-codes", {
      method: "POST",
      body: data,
    }),
  updateAdminPromoCode: (
    id: number,
    data: Partial<{ active: boolean; max_redemptions: number | null; expires_at: string | null }>,
  ) => request<PromoCode>(`/api/v1/admin/promo-codes/${id}`, { method: "PATCH", body: data }),
  listAdminPromoRedemptions: (id: number) =>
    request<PromoRedemption[]>(`/api/v1/admin/promo-codes/${id}/redemptions`),

  // sources
  listPortals: (params?: { category?: string; q?: string }) => {
    const search = new URLSearchParams();
    if (params?.category) search.set("category", params.category);
    if (params?.q) search.set("q", params.q);
    const query = search.toString();
    return request<PortalList>(`/api/v1/portals${query ? `?${query}` : ""}`);
  },
  searchPortals: (data: PortalSearchRequest) =>
    request<PortalSearchResult>("/api/v1/portals/search", { method: "POST", body: data }),
  subscribePortals: (data: PortalSubscribeRequest) =>
    request<PortalSubscribeResult>("/api/v1/portals/subscribe", { method: "POST", body: data }),
  listSources: () => request<Source[]>("/api/v1/sources"),
  detectSource: (url: string, pageTitle?: string) =>
    request<SourceDetectResult>("/api/v1/sources/detect", {
      method: "POST",
      body: { url, page_title: pageTitle ?? null },
    }),
  createSource: (data: SourceCreate) =>
    request<Source>("/api/v1/sources", { method: "POST", body: data }),
  updateSource: (id: number, data: Partial<SourceCreate>) =>
    request<Source>(`/api/v1/sources/${id}`, { method: "PATCH", body: data }),
  deleteSource: (id: number) => request<void>(`/api/v1/sources/${id}`, { method: "DELETE" }),
  testSource: (id: number) =>
    request<SourceTestResult>(`/api/v1/sources/${id}/test`, { method: "POST", body: {} }),

  // searches
  listSearches: () => request<Search[]>("/api/v1/searches"),
  createSearch: (data: SearchCreate) =>
    request<Search>("/api/v1/searches", { method: "POST", body: data }),
  updateSearch: (id: number, data: Partial<SearchCreate>) =>
    request<Search>(`/api/v1/searches/${id}`, { method: "PATCH", body: data }),
  deleteSearch: (id: number) => request<void>(`/api/v1/searches/${id}`, { method: "DELETE" }),
  runSearch: (id: number) =>
    request<SearchRunResult>(`/api/v1/searches/${id}/run`, { method: "POST" }),
  getSearchRun: (id: number) => request<SearchRunResult>(`/api/v1/search-runs/${id}`),

  // jobs
  listJobs: (searchId?: number, status?: string) =>
    request<Job[]>(`/api/v1/jobs${buildJobQuery(searchId, status)}`),
  updateJob: (id: number, data: { status: "seen" | "applied" | "archived" }) =>
    request<Job>(`/api/v1/jobs/${id}`, { method: "PATCH", body: data }),
  applyToJob: (
    id: number,
    data: {
      dry_run?: boolean;
      cover_letter?: string | null;
      tailored_resume_b64?: string | null;
      tailored_resume_artifact_id?: number | null;
    },
  ) => request<JobApplyResult>(`/api/v1/jobs/${id}/apply`, { method: "POST", body: data }),
  generateCoverLetter: (id: number) =>
    request<DocumentGeneration>(`/api/v1/jobs/${id}/generate-cover-letter`, {
      method: "POST",
      body: {},
    }),
  generateResume: (id: number) =>
    request<DocumentGeneration>(`/api/v1/jobs/${id}/generate-resume`, {
      method: "POST",
      body: {},
    }),
  getDocumentGeneration: (id: number) =>
    request<DocumentGeneration>(`/api/v1/document-generations/${id}`),

  listApplicationLogs: (limit = 100) =>
    request<ApplicationLog[]>(`/api/v1/application-logs?limit=${limit}`),
  getApplicationLog: (id: number) => request<ApplicationLog>(`/api/v1/application-logs/${id}`),
  downloadApplicationArtifact: (id: number) =>
    requestBlob(`/api/v1/application-artifacts/${id}/download`),

  listApplications: (stage?: ApplicationPipelineStage) => {
    const query = stage ? `?stage=${encodeURIComponent(stage)}` : "";
    return request<ApplicationPipelineItem[]>(`/api/v1/applications${query}`);
  },

  draftInboxReply: inboxApi.draftReply,
  listInboxReplyDrafts: inboxApi.listReplyDrafts,
  getMailboxCredentials: inboxApi.getMailboxCredentials,
  upsertMailboxCredentials: inboxApi.upsertMailboxCredentials,
  deleteMailboxCredentials: inboxApi.deleteMailboxCredentials,
  testMailbox: inboxApi.testMailbox,
  gmailAuthorize: inboxApi.gmailAuthorize,
  outlookAuthorize: inboxApi.outlookAuthorize,
  yahooAuthorize: inboxApi.yahooAuthorize,

  // feed
  getFeedUrl: () => request<FeedUrl>("/api/v1/feed/url"),
  rotateFeedUrl: () => request<FeedUrl>("/api/v1/feed/rotate", { method: "POST" }),

  // targets
  listTargets: () => request<NotificationTarget[]>("/api/v1/targets"),
  createTarget: (data: TargetCreate) =>
    request<NotificationTarget>("/api/v1/targets", { method: "POST", body: data }),
  updateTarget: (id: number, data: Partial<TargetCreate>) =>
    request<NotificationTarget>(`/api/v1/targets/${id}`, { method: "PATCH", body: data }),
  deleteTarget: (id: number) => request<void>(`/api/v1/targets/${id}`, { method: "DELETE" }),
  testTarget: (id: number) =>
    request<{ external_id: string; status: string; error: string | null }>(
      `/api/v1/targets/${id}/test`,
      { method: "POST" },
    ),

  // site credentials
  listCredentials: () => request<SiteCredential[]>("/api/v1/credentials"),
  createCredential: (data: CredentialCreate) =>
    request<SiteCredential>("/api/v1/credentials", { method: "POST", body: data }),
  updateCredential: (id: number, data: Partial<CredentialCreate>) =>
    request<SiteCredential>(`/api/v1/credentials/${id}`, { method: "PATCH", body: data }),
  deleteCredential: (id: number) =>
    request<void>(`/api/v1/credentials/${id}`, { method: "DELETE" }),

  // application profile (auto-apply candidate data)
  getProfile: () => request<Profile>("/api/v1/profile"),
  saveProfile: (data: ProfileData) =>
    request<Profile>("/api/v1/profile", { method: "PUT", body: data }),
  uploadResume: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return requestForm<Profile>("/api/v1/profile/resume", { method: "PUT", body });
  },
  deleteResume: () => request<Profile>("/api/v1/profile/resume", { method: "DELETE" }),
  uploadResumeTemplate: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return requestForm<Profile>("/api/v1/profile/resume-template", { method: "PUT", body });
  },
  deleteResumeTemplate: () =>
    request<Profile>("/api/v1/profile/resume-template", { method: "DELETE" }),
  deleteProfile: () => request<void>("/api/v1/profile", { method: "DELETE" }),

  // AI summary preferences (Pro)
  getSummaryPreferences: () => request<SummaryPreferences>("/api/v1/summary-preferences"),
  updateSummaryPreferences: (data: SummaryPreferencesUpdate) =>
    request<SummaryPreferences>("/api/v1/summary-preferences", { method: "PATCH", body: data }),
};
