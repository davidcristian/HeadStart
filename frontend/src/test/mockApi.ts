/** Shared mocked API client for page smoke tests. */

import { vi } from "vitest";
import type {
  AdminUser,
  ApplicationLog,
  DataRequestLog,
  Job,
  NotificationTarget,
  Profile,
  ProfileData,
  Search,
  Source,
  User,
} from "../types";
import { emptyProfile, sampleJob, sampleMeta } from "./fixtures";
import {
  emptyAdminStats,
  newPromoCodeRecord,
  newSearchRecord,
  newSourceRecord,
  newTargetRecord,
  sampleApplyJobResult,
  sampleBillingStatus,
  sampleDetectSource,
  sampleFeedUrl,
  samplePortalSearchResult,
  samplePortals,
  sampleRotatedFeedUrl,
  sampleRunSearchResult,
  sampleSubscribePortalsResult,
  sampleTeamUser,
  sampleTestSourceResult,
  sampleUserDataExport,
  updatedPromoCodeRecord,
  updatedSearchRecord,
  updatedSourceRecord,
} from "./mockApiSamples";

const mockApi = vi.hoisted(() => ({
  meta: vi.fn(async () => sampleMeta),
  listPortals: vi.fn(async () => samplePortals),
  searchPortals: vi.fn(async () => samplePortalSearchResult),
  subscribePortals: vi.fn(async () => sampleSubscribePortalsResult),
  listSources: vi.fn(async (): Promise<Source[]> => []),
  detectSource: vi.fn(async () => sampleDetectSource),
  createSource: vi.fn(async (data: unknown) => newSourceRecord(data)),
  updateSource: vi.fn(async (_id: number, data: unknown) => updatedSourceRecord(data)),
  deleteSource: vi.fn(async () => undefined),
  testSource: vi.fn(async () => sampleTestSourceResult),
  listSearches: vi.fn(async (): Promise<Search[]> => []),
  createSearch: vi.fn(async (data: unknown) => newSearchRecord(data)),
  updateSearch: vi.fn(async (_id: number, data: unknown) => updatedSearchRecord(data)),
  deleteSearch: vi.fn(async () => undefined),
  runSearch: vi.fn(async () => sampleRunSearchResult),
  listJobs: vi.fn(async (): Promise<Job[]> => []),
  updateJob: vi.fn(async (_id: number, data: { status: string }) => ({
    ...sampleJob,
    status: data.status,
  })),
  applyToJob: vi.fn(async () => sampleApplyJobResult),
  generateCoverLetter: vi.fn(async () => ({
    cover_letter: "Dear ACME team,\n\nI am excited about the Software Engineer role.",
    provider: "heuristic",
    fallback: false,
  })),
  getFeedUrl: vi.fn(async () => sampleFeedUrl),
  rotateFeedUrl: vi.fn(async () => sampleRotatedFeedUrl),
  listTargets: vi.fn(async (): Promise<NotificationTarget[]> => []),
  createTarget: vi.fn(async (data: unknown) => newTargetRecord(data)),
  deleteTarget: vi.fn(async () => undefined),
  testTarget: vi.fn(async () => ({ external_id: "test-1", status: "sent", error: null })),
  me: vi.fn(async (): Promise<User> => sampleTeamUser),
  completeOnboarding: vi.fn(async (): Promise<User> => ({
    ...sampleTeamUser,
    onboarding_completed_at: "2026-06-28T12:00:00Z",
  })),
  exportMyData: vi.fn(async () => sampleUserDataExport),
  deleteAccount: vi.fn(async () => undefined),
  billingStatus: vi.fn(async () => sampleBillingStatus),
  createCheckout: vi.fn(async () => ({ url: "https://checkout.stripe.test/session" })),
  validatePromoCode: vi.fn(async (code: string) => ({
    code: code.toUpperCase(),
    promo_type: "percent_off" as const,
    description: "20% off",
    trial_days: null,
    percent_off: 20,
    amount_off_cents: null,
    plan_target: null,
  })),
  createBillingPortal: vi.fn(async () => ({ url: "https://billing.stripe.test/portal" })),
  getProfile: vi.fn(async (): Promise<Profile> => emptyProfile),
  saveProfile: vi.fn(async (data: ProfileData): Promise<Profile> => ({
    ...emptyProfile,
    ...data,
    exists: true,
    updated_at: "2026-06-28T12:00:00Z",
    resume_file: null,
  })),
  uploadResume: vi.fn(async (): Promise<Profile> => ({
    ...emptyProfile,
    exists: true,
    updated_at: "2026-06-28T12:00:00Z",
    resume_file: {
      filename: "resume.pdf",
      content_type: "application/pdf",
      size_bytes: 1024,
    },
  })),
  deleteResume: vi.fn(async (): Promise<Profile> => emptyProfile),
  deleteProfile: vi.fn(async () => undefined),
  getSummaryPreferences: vi.fn(async () => ({
    enabled: false,
    server_default_provider: "heuristic",
    selected_provider: null,
    effective_provider: "heuristic" as const,
    has_custom_api_key: false,
    providers: [
      {
        id: "heuristic" as const,
        label: "Built-in",
        description: "Offline filter-based blurbs.",
        requires_api_key: false,
      },
      {
        id: "openai" as const,
        label: "OpenAI",
        description: "OpenAI-compatible API.",
        requires_api_key: true,
      },
      {
        id: "gemini" as const,
        label: "Google Gemini",
        description: "Gemini API.",
        requires_api_key: true,
      },
      {
        id: "anthropic" as const,
        label: "Anthropic Claude",
        description: "Anthropic Messages API.",
        requires_api_key: true,
      },
    ],
  })),
  updateSummaryPreferences: vi.fn(async (data: unknown) => ({
    enabled: true,
    server_default_provider: "heuristic",
    selected_provider: (data as { provider?: string | null }).provider ?? null,
    effective_provider: (data as { provider?: string | null }).provider ?? "heuristic",
    has_custom_api_key: Boolean((data as { api_key?: string }).api_key),
    providers: [
      {
        id: "heuristic" as const,
        label: "Built-in",
        description: "Offline filter-based blurbs.",
        requires_api_key: false,
      },
    ],
  })),
  listApplicationLogs: vi.fn(async (): Promise<ApplicationLog[]> => []),
  getApplicationLog: vi.fn(async (): Promise<ApplicationLog> => ({
    id: 1,
    seen_job_id: sampleJob.id,
    job_title: sampleJob.title,
    job_company: sampleJob.company,
    job_url: sampleJob.url,
    status: "submitted",
    dry_run: false,
    error: null,
    payload: null,
    external_application_id: "app-1",
    created_at: "2026-06-28T12:00:00Z",
  })),
  listAdminUsers: vi.fn(async (): Promise<AdminUser[]> => []),
  updateAdminUser: vi.fn(async (_id: number, data: unknown): Promise<AdminUser> => ({
    id: 2,
    email: "member@example.com",
    is_admin: false,
    is_active: true,
    plan: "free",
    onboarding_completed_at: "2026-06-29T00:00:00Z",
    email_verified_at: "2026-06-29T00:00:00Z",
    created_at: "2026-06-29T00:00:00Z",
    ...(data as object),
  })),
  getAdminStats: vi.fn(async () => emptyAdminStats),
  listAdminDataRequests: vi.fn(async (): Promise<DataRequestLog[]> => []),
  listAdminPromoCodes: vi.fn(async () => []),
  createAdminPromoCode: vi.fn(async (data: unknown) => newPromoCodeRecord(data)),
  updateAdminPromoCode: vi.fn(async (id: number, data: unknown) =>
    updatedPromoCodeRecord(id, data),
  ),
  listAdminPromoRedemptions: vi.fn(async () => []),
}));

vi.mock("../api", () => ({ api: mockApi }));

/** Reset all API mocks to their default empty-list responses. */
export function resetMockApi(): void {
  mockApi.meta.mockResolvedValue(sampleMeta);
  mockApi.listPortals.mockResolvedValue(samplePortals);
  mockApi.listSources.mockResolvedValue([]);
  mockApi.listSearches.mockResolvedValue([]);
  mockApi.listJobs.mockResolvedValue([]);
  mockApi.listTargets.mockResolvedValue([]);
  mockApi.getProfile.mockResolvedValue(emptyProfile);
}

export { mockApi };
