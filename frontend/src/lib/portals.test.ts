import { describe, expect, it } from "vitest";
import { MAX_PORTAL_SELECTION, capPortalIds } from "./portals";

describe("capPortalIds", () => {
  it("returns all ids when under the limit", () => {
    expect(capPortalIds(["a", "b", "c"])).toEqual(new Set(["a", "b", "c"]));
  });

  it("keeps catalog order and stops at MAX_PORTAL_SELECTION", () => {
    const ids = Array.from({ length: MAX_PORTAL_SELECTION + 5 }, (_, i) => `p${i}`);
    const capped = capPortalIds(ids);
    expect(capped.size).toBe(MAX_PORTAL_SELECTION);
    expect([...capped]).toEqual(ids.slice(0, MAX_PORTAL_SELECTION));
  });

  it("honors an explicit lower limit", () => {
    expect(capPortalIds(["a", "b", "c"], 2)).toEqual(new Set(["a", "b"]));
  });
});
