/** Shared mocked API client for page smoke tests. */

import { vi } from "vitest";
import type { Job, NotificationTarget, Search, Source } from "../types";

const mockApi = vi.hoisted(() => ({
  meta: vi.fn(async () => ({
    scrapers: ["greenhouse", "lever", "ashby", "generic_html", "playwright"],
    notifiers: ["discord", "email", "ntfy", "slack", "telegram"],
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
    enabled: true,
    last_run_at: null,
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
    enabled: true,
    last_run_at: "2026-06-28T12:00:00Z",
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
    error: null,
  })),
  listJobs: vi.fn(async (): Promise<Job[]> => []),
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
