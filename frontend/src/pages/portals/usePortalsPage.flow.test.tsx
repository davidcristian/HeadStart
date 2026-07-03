import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePortalsPage } from "./usePortalsPage";

const searchMutate = vi.hoisted(() => vi.fn());
const subscribeMutate = vi.hoisted(() => vi.fn());
const targetsData = vi.hoisted(() => ({ value: [] as unknown[] }));

vi.mock("../../hooks/queries", () => ({
  useMeta: () => ({ data: { plan: { plan: "pro", features: { portal_search: true } } } }),
  usePortals: () => ({
    data: {
      items: [{ id: "stripe", allowed_on_plan: true }],
      categories: ["unicorn"],
    },
  }),
  useTargets: () => ({ data: targetsData.value }),
}));

vi.mock("../../hooks/mutations", () => ({
  useSearchPortals: () => ({ mutateAsync: searchMutate }),
  useSubscribePortals: () => ({ mutateAsync: subscribeMutate }),
}));

const searchResult = {
  items: [],
  portals_searched: 1,
  portals_failed: 0,
  errors: [],
};

describe("usePortalsPage runSearch", () => {
  beforeEach(() => {
    searchMutate.mockReset();
    subscribeMutate.mockReset();
    targetsData.value = [];
  });

  it("requires keywords before searching", async () => {
    const { result } = renderHook(() => usePortalsPage());
    await act(async () => {
      await result.current.runSearch();
    });
    expect(result.current.error).toBe("Enter keywords to search across company portals.");
    expect(searchMutate).not.toHaveBeenCalled();
  });

  it("requires at least one selected portal", async () => {
    const { result } = renderHook(() => usePortalsPage());
    act(() => {
      result.current.setKeywords("engineer");
      result.current.setSelectedIds(new Set());
    });
    await act(async () => {
      await result.current.runSearch();
    });
    expect(result.current.error).toBe("Select at least one company portal.");
  });

  it("runs a search and stores results, forwarding optional filters", async () => {
    searchMutate.mockResolvedValue(searchResult);
    const { result } = renderHook(() => usePortalsPage());
    await waitFor(() => expect(result.current.selectedIds.size).toBe(1));

    act(() => {
      result.current.setKeywords(" engineer ");
      result.current.setLocation(" remote ");
      result.current.setWorkplace("remote");
      result.current.setCategory("unicorn");
    });
    await act(async () => {
      await result.current.runSearch();
    });

    expect(searchMutate).toHaveBeenCalledWith({
      keywords: "engineer",
      category: "unicorn",
      portal_ids: ["stripe"],
      location: "remote",
      workplace: "remote",
    });
    expect(result.current.results).toEqual(searchResult);
  });

  it("captures search errors", async () => {
    searchMutate.mockRejectedValue(new Error("search boom"));
    const { result } = renderHook(() => usePortalsPage());
    act(() => result.current.setKeywords("engineer"));
    await act(async () => {
      await result.current.runSearch();
    });
    expect(result.current.error).toBe("search boom");
  });
});

describe("usePortalsPage createAlerts", () => {
  beforeEach(() => {
    searchMutate.mockReset();
    subscribeMutate.mockReset();
    targetsData.value = [];
  });

  it("requires keywords", async () => {
    const { result } = renderHook(() => usePortalsPage());
    await act(async () => {
      await result.current.createAlerts();
    });
    expect(result.current.error).toBe("Enter keywords before creating alerts.");
  });

  it("requires a selected portal", async () => {
    const { result } = renderHook(() => usePortalsPage());
    act(() => {
      result.current.setKeywords("engineer");
      result.current.setSelectedIds(new Set());
    });
    await act(async () => {
      await result.current.createAlerts();
    });
    expect(result.current.error).toBe("Select at least one company portal.");
  });

  it("requires a notification target", async () => {
    const { result } = renderHook(() => usePortalsPage());
    act(() => result.current.setKeywords("engineer"));
    await act(async () => {
      await result.current.createAlerts();
    });
    expect(result.current.error).toBe("Pick a notification target for new alerts.");
  });

  it("builds a plural success notice with a message", async () => {
    subscribeMutate.mockResolvedValue({
      searches_created: 2,
      sources_created: 3,
      search_ids: [1, 2],
      skipped_portal_ids: ["a", "b"],
      message: "All set",
    });
    const { result } = renderHook(() => usePortalsPage());
    act(() => {
      result.current.setKeywords("engineer");
      result.current.setTargetId(10);
      result.current.setInterval(1800);
    });
    await act(async () => {
      await result.current.createAlerts();
    });

    expect(subscribeMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        keywords: "engineer",
        portal_ids: ["stripe"],
        target_id: 10,
        interval_seconds: 1800,
      }),
    );
    expect(result.current.notice).toBe(
      "Created 2 searches; added 3 sources; skipped 2 duplicates. All set",
    );
  });

  it("builds a singular success notice without a message", async () => {
    subscribeMutate.mockResolvedValue({
      searches_created: 1,
      sources_created: 1,
      search_ids: [1],
      skipped_portal_ids: ["a"],
      message: null,
    });
    const { result } = renderHook(() => usePortalsPage());
    act(() => {
      result.current.setKeywords("engineer");
      result.current.setTargetId(10);
    });
    await act(async () => {
      await result.current.createAlerts();
    });
    expect(result.current.notice).toBe("Created 1 search; added 1 source; skipped 1 duplicate.");
  });

  it("omits zero-count clauses from the notice", async () => {
    subscribeMutate.mockResolvedValue({
      searches_created: 0,
      sources_created: 0,
      search_ids: [],
      skipped_portal_ids: [],
      message: null,
    });
    const { result } = renderHook(() => usePortalsPage());
    act(() => {
      result.current.setKeywords("engineer");
      result.current.setTargetId(10);
    });
    await act(async () => {
      await result.current.createAlerts();
    });
    expect(result.current.notice).toBe(".");
  });

  it("captures subscribe errors", async () => {
    subscribeMutate.mockRejectedValue(new Error("subscribe boom"));
    const { result } = renderHook(() => usePortalsPage());
    act(() => {
      result.current.setKeywords("engineer");
      result.current.setTargetId(10);
    });
    await act(async () => {
      await result.current.createAlerts();
    });
    expect(result.current.error).toBe("subscribe boom");
  });
});
