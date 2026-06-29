/** Shared mocked API client for page smoke tests. */

import { vi } from "vitest";
import type {
  AdminStats,
  AdminUser,
  Job,
  NotificationTarget,
  Search,
  Source,
  User,
} from "../types";
import { sampleJob } from "./fixtures";

const mockApi = vi.hoisted(() => ({
  meta: vi.fn(async () => ({
    scrapers: [
      "greenhouse",
      "lever",
      "ashby",
      "workday",
      "indeed",
      "linkedin",
      "generic_html",
      "playwright",
    ],
    notifiers: ["discord", "email", "ntfy", "slack", "telegram", "webhook"],
  })),
  listSources: vi.fn(async (): Promise<Source[]> => []),
  createSource: vi.fn(async (data: unknown) => ({
    id: 99,
    name: "New source",
    adapter_key: "greenhouse",
    base_url: "",
    default_config: {},
    enabled: true,
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  })),
  updateSource: vi.fn(async (_id: number, data: unknown) => ({
    id: 1,
    name: "ACME Careers",
    adapter_key: "greenhouse",
    base_url: "https://boards.greenhouse.io/acme",
    default_config: {},
    enabled: true,
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  })),
  deleteSource: vi.fn(async () => undefined),
  testSource: vi.fn(async () => ({
    ok: true,
    found: 2,
    sample: [{ external_id: "1", title: "Engineer", company: "ACME", location: "", url: "" }],
    error: null,
  })),
  listSearches: vi.fn(async (): Promise<Search[]> => []),
  createSearch: vi.fn(async (data: unknown) => ({
    id: 99,
    name: "New search",
    source_id: 1,
    target_id: null,
    query_url: "",
    filters: {},
    config: {},
    interval_seconds: 900,
    notification_mode: "immediate",
    digest_interval_seconds: 3600,
    enabled: true,
    last_run_at: null,
    last_digest_at: null,
    last_error: null,
    next_run_at: "2026-06-28T12:15:00Z",
    created_at: "2026-06-28T00:00:00Z",
    recent_delivery_failures: [],
    ...(data as object),
  })),
  updateSearch: vi.fn(async (_id: number, data: unknown) => ({
    id: 20,
    name: "Google SWE",
    source_id: 1,
    target_id: 10,
    query_url: "https://example.test/jobs",
    filters: {},
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
    ...(data as object),
  })),
  deleteSearch: vi.fn(async () => undefined),
  runSearch: vi.fn(async () => ({
    search_id: 20,
    found: 3,
    new: 1,
    notified: 1,
    failed: 0,
    skipped: 0,
    filtered: 0,
    queued: 0,
    closed: 0,
    error: null,
  })),
  listJobs: vi.fn(async (): Promise<Job[]> => []),
  updateJob: vi.fn(async (_id: number, data: { status: string }) => ({
    ...sampleJob,
    status: data.status,
  })),
  getFeedUrl: vi.fn(async () => ({
    url: "http://localhost:8000/api/v1/feed/rss?token=test-token",
    token: "test-token",
  })),
  rotateFeedUrl: vi.fn(async () => ({
    url: "http://localhost:8000/api/v1/feed/rss?token=rotated-token",
    token: "rotated-token",
  })),
  listTargets: vi.fn(async (): Promise<NotificationTarget[]> => []),
  createTarget: vi.fn(async (data: unknown) => ({
    id: 99,
    name: "New target",
    type: "ntfy",
    config: {},
    created_at: "2026-06-28T00:00:00Z",
    ...(data as object),
  })),
  deleteTarget: vi.fn(async () => undefined),
  testTarget: vi.fn(async () => ({ external_id: "test-1", status: "sent", error: null })),
  me: vi.fn(async (): Promise<User> => ({
    id: 1,
    email: "admin@example.com",
    is_admin: true,
    is_active: true,
    created_at: "2026-06-28T00:00:00Z",
  })),
  listAdminUsers: vi.fn(async (): Promise<AdminUser[]> => []),
  updateAdminUser: vi.fn(async (_id: number, data: unknown): Promise<AdminUser> => ({
    id: 2,
    email: "member@example.com",
    is_admin: false,
    is_active: true,
    created_at: "2026-06-29T00:00:00Z",
    ...(data as object),
  })),
  getAdminStats: vi.fn(async (): Promise<AdminStats> => ({
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
  })),
}));

vi.mock("../api", () => ({ api: mockApi }));

import { sampleMeta } from "./fixtures";

/** Reset all API mocks to their default empty-list responses. */
export function resetMockApi(): void {
  mockApi.meta.mockResolvedValue(sampleMeta);
  mockApi.listSources.mockResolvedValue([]);
  mockApi.listSearches.mockResolvedValue([]);
  mockApi.listJobs.mockResolvedValue([]);
  mockApi.listTargets.mockResolvedValue([]);
}

export { mockApi };
