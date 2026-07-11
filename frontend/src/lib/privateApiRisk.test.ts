import { describe, expect, it } from "vitest";
import {
  isPrivateApiRiskAdapter,
  PRIVATE_API_APPLY_RISK_CONFIRM,
  PRIVATE_API_CREDENTIAL_RISK_CONFIRM,
  PRIVATE_API_RISK_ADAPTERS,
} from "./privateApiRisk";

describe("privateApiRisk", () => {
  it("flags only linkedin and indeed adapters", () => {
    expect(PRIVATE_API_RISK_ADAPTERS.has("linkedin")).toBe(true);
    expect(PRIVATE_API_RISK_ADAPTERS.has("indeed")).toBe(true);
    expect(isPrivateApiRiskAdapter("linkedin")).toBe(true);
    expect(isPrivateApiRiskAdapter("indeed")).toBe(true);
    expect(isPrivateApiRiskAdapter("greenhouse")).toBe(false);
  });

  it("exposes distinct confirm copy for apply vs credentials", () => {
    expect(PRIVATE_API_APPLY_RISK_CONFIRM).toMatch(/Easy Apply/);
    expect(PRIVATE_API_CREDENTIAL_RISK_CONFIRM).toMatch(/session cookies/);
    expect(PRIVATE_API_APPLY_RISK_CONFIRM).not.toEqual(PRIVATE_API_CREDENTIAL_RISK_CONFIRM);
  });
});
