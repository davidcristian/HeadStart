import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import type { MockInstance } from "vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  createSource: vi.fn(async () => ({ id: 1 })),
  updateSource: vi.fn(async () => ({ id: 1 })),
  deleteSource: vi.fn(async () => undefined),
  testSource: vi.fn(async () => ({ ok: true })),
  createSearch: vi.fn(async () => ({ id: 1 })),
  updateSearch: vi.fn(async () => ({ id: 1 })),
  deleteSearch: vi.fn(async () => undefined),
  runSearch: vi.fn(async () => ({
    id: 1,
    search_id: 1,
    status: "ready",
    found: 0,
    new: 0,
    notified: 0,
    failed: 0,
    skipped: 0,
    filtered: 0,
    queued: 0,
    closed: 0,
    error: null,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  })),
  createTarget: vi.fn(async () => ({ id: 1 })),
  deleteTarget: vi.fn(async () => undefined),
  testTarget: vi.fn(async () => ({ status: "sent" })),
  createCredential: vi.fn(async () => ({ id: 1 })),
  updateCredential: vi.fn(async () => ({ id: 1 })),
  deleteCredential: vi.fn(async () => undefined),
  saveProfile: vi.fn(async () => ({ exists: true })),
  deleteProfile: vi.fn(async () => undefined),
  uploadResume: vi.fn(async () => ({ exists: true })),
  deleteResume: vi.fn(async () => ({ exists: false })),
  uploadResumeTemplate: vi.fn(async () => ({ exists: true })),
  deleteResumeTemplate: vi.fn(async () => ({ exists: false })),
  rotateFeedUrl: vi.fn(async () => ({ url: "u" })),
  updateAdminUser: vi.fn(async () => ({ id: 1 })),
  searchPortals: vi.fn(async () => ({ portals: [] })),
  subscribePortals: vi.fn(async () => ({ created: 1 })),
  draftInboxReply: vi.fn(async () => ({ draft: "hi" })),
}));
const pollSearchRun = vi.hoisted(() =>
  vi.fn(async () => ({
    id: 9,
    search_id: 2,
    status: "ready",
    found: 2,
    new: 1,
    notified: 1,
    failed: 0,
    skipped: 0,
    filtered: 0,
    queued: 0,
    closed: 0,
    error: null,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:01Z",
  })),
);
vi.mock("../api", () => ({ api }));
vi.mock("../api/pollSearchRun", () => ({ pollSearchRun }));

import * as mutations from "./mutations";

let client: QueryClient;
let invalidateSpy: MockInstance<QueryClient["invalidateQueries"]>;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function keys(): unknown[] {
  return invalidateSpy.mock.calls.map((c) => (c[0] as { queryKey: unknown }).queryKey);
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockClear());
  pollSearchRun.mockClear();
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  invalidateSpy = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
});

async function run<V>(useHook: () => { mutateAsync: (v: V) => Promise<unknown> }, variables: V) {
  const { result } = renderHook(useHook, { wrapper });
  await act(async () => {
    await result.current.mutateAsync(variables);
  });
}

describe("source mutations", () => {
  it("create invalidates sources + meta", async () => {
    await run(mutations.useCreateSource, {} as never);
    expect(api.createSource).toHaveBeenCalled();
    expect(keys()).toEqual(expect.arrayContaining([["sources"], ["meta"]]));
  });

  it("update invalidates sources", async () => {
    await run(mutations.useUpdateSource, { id: 1, data: {} });
    expect(api.updateSource).toHaveBeenCalledWith(1, {});
    expect(keys()).toContainEqual(["sources"]);
  });

  it("delete invalidates sources + meta", async () => {
    await run(mutations.useDeleteSource, 1);
    expect(keys()).toEqual(expect.arrayContaining([["sources"], ["meta"]]));
  });

  it("test source does not invalidate", async () => {
    await run(mutations.useTestSource, 1);
    expect(api.testSource).toHaveBeenCalledWith(1);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});

describe("search mutations", () => {
  it("create invalidates searches + meta", async () => {
    await run(mutations.useCreateSearch, {} as never);
    expect(keys()).toEqual(expect.arrayContaining([["searches"], ["meta"]]));
  });

  it("update invalidates searches", async () => {
    await run(mutations.useUpdateSearch, { id: 2, data: {} });
    expect(api.updateSearch).toHaveBeenCalledWith(2, {});
    expect(keys()).toContainEqual(["searches"]);
  });

  it("delete invalidates searches + meta", async () => {
    await run(mutations.useDeleteSearch, 2);
    expect(keys()).toEqual(expect.arrayContaining([["searches"], ["meta"]]));
  });

  it("run invalidates searches and jobs", async () => {
    await run(mutations.useRunSearch, 2);
    expect(keys()).toEqual(expect.arrayContaining([["searches"], ["jobs", null, null]]));
  });

  it("run polls when the enqueue response is still queued", async () => {
    api.runSearch.mockResolvedValueOnce({
      id: 9,
      search_id: 2,
      status: "queued",
      found: 0,
      new: 0,
      notified: 0,
      failed: 0,
      skipped: 0,
      filtered: 0,
      queued: 0,
      closed: 0,
      error: null,
      created_at: "2026-07-10T00:00:00Z",
      updated_at: "2026-07-10T00:00:00Z",
    });
    await run(mutations.useRunSearch, 2);
    expect(pollSearchRun).toHaveBeenCalledWith(9);
  });
});

describe("target mutations", () => {
  it("create invalidates targets + meta", async () => {
    await run(mutations.useCreateTarget, {} as never);
    expect(keys()).toEqual(expect.arrayContaining([["targets"], ["meta"]]));
  });

  it("delete invalidates targets + meta", async () => {
    await run(mutations.useDeleteTarget, 3);
    expect(keys()).toEqual(expect.arrayContaining([["targets"], ["meta"]]));
  });

  it("test target does not invalidate", async () => {
    await run(mutations.useTestTarget, 3);
    expect(api.testTarget).toHaveBeenCalledWith(3);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});

describe("credential mutations", () => {
  it("create invalidates credentials", async () => {
    await run(mutations.useCreateCredential, {} as never);
    expect(keys()).toContainEqual(["credentials"]);
  });

  it("update invalidates credentials", async () => {
    await run(mutations.useUpdateCredential, { id: 4, data: {} });
    expect(api.updateCredential).toHaveBeenCalledWith(4, {});
    expect(keys()).toContainEqual(["credentials"]);
  });

  it("delete invalidates credentials", async () => {
    await run(mutations.useDeleteCredential, 4);
    expect(keys()).toContainEqual(["credentials"]);
  });
});

describe("profile mutations", () => {
  it("save / delete / resume / template all invalidate profile", async () => {
    await run(mutations.useSaveProfile, {} as never);
    await run(mutations.useDeleteProfile, undefined as never);
    await run(mutations.useUploadResume, new File(["x"], "r.pdf"));
    await run(mutations.useDeleteResume, undefined as never);
    await run(mutations.useUploadResumeTemplate, new File(["x"], "r.tex"));
    await run(mutations.useDeleteResumeTemplate, undefined as never);
    expect(api.saveProfile).toHaveBeenCalled();
    expect(api.uploadResume).toHaveBeenCalled();
    expect(api.uploadResumeTemplate).toHaveBeenCalled();
    expect(keys()).toEqual(
      expect.arrayContaining([["profile"], ["profile"], ["profile"], ["profile"]]),
    );
  });
});

describe("misc mutations", () => {
  it("rotate feed url invalidates the feed url", async () => {
    await run(mutations.useRotateFeedUrl, undefined as never);
    expect(keys()).toContainEqual(["feed-url"]);
  });

  it("update admin user invalidates admin users + meta", async () => {
    await run(mutations.useUpdateAdminUser, { id: 1, patch: { is_active: false } });
    expect(api.updateAdminUser).toHaveBeenCalledWith(1, { is_active: false });
    expect(keys()).toEqual(expect.arrayContaining([["admin", "users"], ["meta"]]));
  });

  it("search portals does not invalidate", async () => {
    await run(mutations.useSearchPortals, {} as never);
    expect(api.searchPortals).toHaveBeenCalled();
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("subscribe portals invalidates sources, searches, portals and meta", async () => {
    await run(mutations.useSubscribePortals, {} as never);
    expect(keys()).toEqual(
      expect.arrayContaining([["sources"], ["searches"], ["portals"], ["meta"]]),
    );
  });

  it("draft inbox reply invalidates the applications pipeline", async () => {
    await run(mutations.useDraftInboxReply, { classification_id: 1 });
    expect(api.draftInboxReply).toHaveBeenCalledWith({ classification_id: 1 });
    expect(keys()).toContainEqual(["applications"]);
  });
});

describe("re-exports", () => {
  it("re-exports the job mutation hooks", () => {
    expect(mutations.useApplyToJob).toBeTypeOf("function");
    expect(mutations.useGenerateCoverLetter).toBeTypeOf("function");
    expect(mutations.useGenerateResume).toBeTypeOf("function");
    expect(mutations.useUpdateJob).toBeTypeOf("function");
  });
});
