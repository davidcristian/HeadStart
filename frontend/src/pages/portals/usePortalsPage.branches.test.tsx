import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePortalsPage } from "./usePortalsPage";

// Mutable query mock values so each test can drive the fallback branches
// (missing `meta.data`, missing `portals.data`, missing `targets.data`) that
// the other portals hook specs never exercise.
const metaData = vi.hoisted(() => ({ value: undefined as unknown }));
const portalsData = vi.hoisted(() => ({ value: undefined as unknown }));
const targetsData = vi.hoisted(() => ({ value: undefined as unknown }));
const searchMutate = vi.hoisted(() => vi.fn());
const subscribeMutate = vi.hoisted(() => vi.fn());

vi.mock("../../hooks/queries", () => ({
  useMeta: () => ({ data: metaData.value }),
  usePortals: () => ({ data: portalsData.value }),
  useTargets: () => ({ data: targetsData.value }),
}));

vi.mock("../../hooks/mutations", () => ({
  useSearchPortals: () => ({ mutateAsync: searchMutate }),
  useSubscribePortals: () => ({ mutateAsync: subscribeMutate }),
}));

function portalsPayload(ids: Array<{ id: string; allowed_on_plan: boolean }>) {
  return { items: ids, categories: ["unicorn"] };
}

describe("usePortalsPage fallbacks", () => {
  beforeEach(() => {
    metaData.value = undefined;
    portalsData.value = undefined;
    targetsData.value = undefined;
    searchMutate.mockReset();
    subscribeMutate.mockReset();
  });

  it("falls back to defaults when meta, portals, and targets have no data", () => {
    const { result } = renderHook(() => usePortalsPage());
    expect(result.current.plan).toBe("free");
    expect(result.current.portalSearchAllowed).toBe(false);
    expect(result.current.categories).toEqual([]);
    expect(result.current.targets).toEqual([]);
    expect(result.current.catalogItems).toEqual([]);
    expect(result.current.selectedIds).toEqual(new Set());
  });

  it("reads plan features and drops portals not allowed on the plan", () => {
    metaData.value = { plan: { plan: "pro", features: { portal_search: true } } };
    portalsData.value = portalsPayload([
      { id: "stripe", allowed_on_plan: true },
      { id: "blocked", allowed_on_plan: false },
    ]);
    const { result } = renderHook(() => usePortalsPage());
    expect(result.current.plan).toBe("pro");
    expect(result.current.portalSearchAllowed).toBe(true);
    expect(result.current.categories).toEqual(["unicorn"]);
    expect(result.current.catalogItems.map((p) => p.id)).toEqual(["stripe"]);
    expect(result.current.selectedIds).toEqual(new Set(["stripe"]));
  });

  it("re-adds a portal when toggled back on after deselecting", () => {
    portalsData.value = portalsPayload([{ id: "stripe", allowed_on_plan: true }]);
    const { result } = renderHook(() => usePortalsPage());
    expect(result.current.selectedIds).toEqual(new Set(["stripe"]));

    act(() => result.current.togglePortal("stripe"));
    expect(result.current.selectedIds).toEqual(new Set());

    act(() => result.current.togglePortal("stripe"));
    expect(result.current.selectedIds).toEqual(new Set(["stripe"]));
  });

  it("omits category, location, and workplace from the payload when empty", async () => {
    searchMutate.mockResolvedValue({ items: [] });
    portalsData.value = portalsPayload([{ id: "stripe", allowed_on_plan: true }]);
    const { result } = renderHook(() => usePortalsPage());
    await waitFor(() => expect(result.current.selectedIds.size).toBe(1));

    act(() => result.current.setKeywords("engineer"));
    await act(async () => {
      await result.current.runSearch();
    });

    expect(searchMutate).toHaveBeenCalledWith({
      keywords: "engineer",
      portal_ids: ["stripe"],
    });
  });

  it("subscribes without optional filters and reports the singular-plural notice edge", async () => {
    subscribeMutate.mockResolvedValue({
      searches_created: 0,
      sources_created: 2,
      skipped_portal_ids: [],
      message: "done",
    });
    portalsData.value = portalsPayload([{ id: "stripe", allowed_on_plan: true }]);
    targetsData.value = [];
    const { result } = renderHook(() => usePortalsPage());
    await waitFor(() => expect(result.current.selectedIds.size).toBe(1));

    act(() => {
      result.current.setKeywords("engineer");
      result.current.setTargetId(7);
    });
    await act(async () => {
      await result.current.createAlerts();
    });

    expect(subscribeMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        keywords: "engineer",
        portal_ids: ["stripe"],
        target_id: 7,
        interval_seconds: 900,
      }),
    );
    expect(result.current.notice).toBe("added 2 sources. done");
  });
});
