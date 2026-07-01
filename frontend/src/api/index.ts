/** Typed API endpoints. One function per backend route. */

import type {
  AccessTokenResponse,
  AdminStats,
  AdminUser,
  CredentialCreate,
  Health,
  Job,
  FeedUrl,
  Meta,
  NotificationTarget,
  Profile,
  ProfileData,
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
} from "../types";
import { request } from "./client";

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
  me: () => request<User>("/api/v1/auth/me"),
  completeOnboarding: () =>
    request<User>("/api/v1/auth/me/complete-onboarding", { method: "POST" }),
  exportMyData: () => request<UserDataExport>("/api/v1/auth/me/export"),
  deleteAccount: (password: string) =>
    request<void>("/api/v1/auth/me", { method: "DELETE", body: { password } }),

  // billing
  billingStatus: () => request<BillingStatus>("/api/v1/billing/status"),
  createCheckout: (billingPeriod: BillingPeriod = "monthly") =>
    request<{ url: string }>("/api/v1/billing/checkout", {
      method: "POST",
      body: { plan: "pro", billing_period: billingPeriod },
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

  // sources
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

  // jobs
  listJobs: (searchId?: number, status?: string) =>
    request<Job[]>(`/api/v1/jobs${buildJobQuery(searchId, status)}`),
  updateJob: (id: number, data: { status: "seen" | "applied" | "archived" }) =>
    request<Job>(`/api/v1/jobs/${id}`, { method: "PATCH", body: data }),

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
  deleteProfile: () => request<void>("/api/v1/profile", { method: "DELETE" }),
};
