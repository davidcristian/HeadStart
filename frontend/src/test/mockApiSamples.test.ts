import { describe, expect, it } from "vitest";

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

describe("mockApiSamples record builders", () => {
  it("merges overrides over the default source records", () => {
    expect(newSourceRecord({ name: "X" })).toMatchObject({ id: 99, name: "X" });
    expect(updatedSourceRecord({ enabled: false })).toMatchObject({ id: 1, enabled: false });
  });

  it("merges overrides over the default search records", () => {
    expect(newSearchRecord({ name: "S" })).toMatchObject({ id: 99, name: "S" });
    expect(updatedSearchRecord({ id: 21 })).toMatchObject({ id: 21, name: "Google SWE" });
  });

  it("merges overrides over target and promo-code records", () => {
    expect(newTargetRecord({ type: "discord" })).toMatchObject({ id: 99, type: "discord" });
    expect(newPromoCodeRecord({ code: "A" })).toMatchObject({ id: 1, code: "A" });
    expect(updatedPromoCodeRecord(7, { active: false })).toMatchObject({ id: 7, active: false });
  });
});

describe("mockApiSamples static payloads", () => {
  it("exposes well-formed sample data", () => {
    expect(samplePortals.items[0].id).toBe("stripe");
    expect(samplePortalSearchResult.portals_searched).toBe(1);
    expect(sampleSubscribePortalsResult.search_ids).toContain(42);
    expect(sampleDetectSource.adapter_key).toBe("greenhouse");
    expect(sampleTeamUser.is_admin).toBe(true);
    expect(sampleUserDataExport.format_version).toBe(1);
    expect(emptyAdminStats.users_total).toBe(0);
    expect(sampleBillingStatus.plan).toBe("free");
    expect(sampleRunSearchResult.search_id).toBe(20);
    expect(sampleApplyJobResult.status).toBe("dry_run");
    expect(sampleFeedUrl.token).toBe("test-token");
    expect(sampleRotatedFeedUrl.token).toBe("rotated-token");
    expect(sampleTestSourceResult.ok).toBe(true);
  });
});
