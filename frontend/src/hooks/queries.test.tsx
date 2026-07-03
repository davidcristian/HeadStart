import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  health: vi.fn(async () => ({ status: "ok" })),
  meta: vi.fn(async () => ({ meta: true })),
  me: vi.fn(async () => ({ id: 1 })),
  listSources: vi.fn(async () => []),
  listPortals: vi.fn(async () => ({ portals: [] })),
  listSearches: vi.fn(async () => []),
  listTargets: vi.fn(async () => []),
  listCredentials: vi.fn(async () => []),
  getProfile: vi.fn(async () => ({ exists: false })),
  listApplicationLogs: vi.fn(async () => []),
  listApplications: vi.fn(async () => []),
  getFeedUrl: vi.fn(async () => ({ url: "u" })),
  listJobs: vi.fn(async () => []),
  listAdminUsers: vi.fn(async () => []),
  getAdminStats: vi.fn(async () => ({})),
  listAdminDataRequests: vi.fn(async () => []),
}));
vi.mock("../api", () => ({ api }));

import {
  queryKeys,
  useAdminDataRequests,
  useAdminStats,
  useAdminUsers,
  useApplicationLogs,
  useApplications,
  useCredentials,
  useFeedUrl,
  useHealth,
  useJobs,
  useMe,
  useMeta,
  usePortals,
  useProfile,
  useSearches,
  useSources,
  useTargets,
} from "./queries";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

async function expectQuery<T>(hook: () => { isSuccess: boolean } & T) {
  const { result } = renderHook(hook, { wrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  return result;
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockClear());
});

describe("queryKeys", () => {
  it("builds portal keys with and without filters", () => {
    expect(queryKeys.portals()).toEqual(["portals", null, null]);
    expect(queryKeys.portals("tech", "acme")).toEqual(["portals", "tech", "acme"]);
  });

  it("builds application keys with and without a stage", () => {
    expect(queryKeys.applications()).toEqual(["applications", null]);
    expect(queryKeys.applications("awaiting_reply")).toEqual(["applications", "awaiting_reply"]);
  });

  it("builds job keys with and without search id / status", () => {
    expect(queryKeys.jobs()).toEqual(["jobs", null, null]);
    expect(queryKeys.jobs(3, "new")).toEqual(["jobs", 3, "new"]);
  });
});

describe("read hooks", () => {
  it("useHealth / useMeta / useMe", async () => {
    await expectQuery(useHealth);
    expect(api.health).toHaveBeenCalled();
    await expectQuery(useMeta);
    expect(api.meta).toHaveBeenCalled();
    await expectQuery(useMe);
    expect(api.me).toHaveBeenCalled();
  });

  it("resource lists", async () => {
    await expectQuery(useSources);
    await expectQuery(useSearches);
    await expectQuery(useTargets);
    await expectQuery(useCredentials);
    await expectQuery(useProfile);
    expect(api.listSources).toHaveBeenCalled();
    expect(api.getProfile).toHaveBeenCalled();
  });

  it("usePortals forwards filters to the api", async () => {
    await expectQuery(() => usePortals("tech", "acme"));
    expect(api.listPortals).toHaveBeenCalledWith({ category: "tech", q: "acme" });
  });

  it("useApplicationLogs uses the default and custom limit", async () => {
    await expectQuery(() => useApplicationLogs());
    expect(api.listApplicationLogs).toHaveBeenCalledWith(100);
    await expectQuery(() => useApplicationLogs(25));
    expect(api.listApplicationLogs).toHaveBeenCalledWith(25);
  });

  it("useApplications forwards the stage", async () => {
    await expectQuery(() => useApplications("awaiting_reply"));
    expect(api.listApplications).toHaveBeenCalledWith("awaiting_reply");
  });

  it("useFeedUrl runs when enabled and is idle when disabled", async () => {
    await expectQuery(() => useFeedUrl());
    expect(api.getFeedUrl).toHaveBeenCalledTimes(1);

    const { result } = renderHook(() => useFeedUrl(false), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getFeedUrl).toHaveBeenCalledTimes(1);
  });

  it("useJobs forwards search id and status", async () => {
    await expectQuery(() => useJobs(3, "new"));
    expect(api.listJobs).toHaveBeenCalledWith(3, "new");
  });

  it("admin hooks", async () => {
    await expectQuery(useAdminUsers);
    await expectQuery(useAdminStats);
    await expectQuery(() => useAdminDataRequests());
    expect(api.listAdminDataRequests).toHaveBeenCalledWith(100);
    await expectQuery(() => useAdminDataRequests(5));
    expect(api.listAdminDataRequests).toHaveBeenCalledWith(5);
  });
});
