import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { usePortalsPage } from "./usePortalsPage";

const mockUsePortals = vi.hoisted(() => vi.fn());

vi.mock("../../hooks/queries", () => ({
  useMeta: () => ({ data: { plan: { plan: "pro", features: { portal_search: true } } } }),
  usePortals: () => mockUsePortals(),
  useTargets: () => ({ data: [] }),
}));

vi.mock("../../hooks/mutations", () => ({
  useSearchPortals: () => ({ mutateAsync: vi.fn() }),
  useSubscribePortals: () => ({ mutateAsync: vi.fn() }),
}));

// Minimal catalog items — the hook only reads `id` and `allowed_on_plan`.
function catalog(ids: string[]) {
  return {
    data: {
      items: ids.map((id) => ({ id, allowed_on_plan: true })),
      categories: [],
    },
  };
}

describe("usePortalsPage selection", () => {
  it("preserves manual deselection across a refetch of the same catalog", () => {
    mockUsePortals.mockReturnValue(catalog(["stripe", "meta"]));
    const { result, rerender } = renderHook(() => usePortalsPage());

    expect(result.current.selectedIds).toEqual(new Set(["stripe", "meta"]));

    act(() => result.current.togglePortal("meta"));
    expect(result.current.selectedIds).toEqual(new Set(["stripe"]));

    // A plain refetch returns the same portals with a new array reference.
    mockUsePortals.mockReturnValue(catalog(["stripe", "meta"]));
    rerender();

    expect(result.current.selectedIds).toEqual(new Set(["stripe"]));
  });

  it("re-selects all when the available catalog changes (e.g. a new category)", () => {
    mockUsePortals.mockReturnValue(catalog(["stripe", "meta"]));
    const { result, rerender } = renderHook(() => usePortalsPage());

    act(() => result.current.togglePortal("meta"));
    expect(result.current.selectedIds).toEqual(new Set(["stripe"]));

    mockUsePortals.mockReturnValue(catalog(["google", "apple"]));
    rerender();

    expect(result.current.selectedIds).toEqual(new Set(["google", "apple"]));
  });
});
