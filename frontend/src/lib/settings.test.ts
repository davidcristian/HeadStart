import { beforeEach, describe, expect, it } from "vitest";
import {
  clearTokens,
  getAccessToken,
  getApiBaseUrl,
  getRefreshToken,
  setApiBaseUrl,
  setTokens,
} from "./settings";

describe("settings", () => {
  beforeEach(() => localStorage.clear());

  it("strips trailing slashes from the base URL", () => {
    setApiBaseUrl("http://example.test/");
    expect(getApiBaseUrl()).toBe("http://example.test");
  });

  it("persists access and refresh tokens", () => {
    setTokens("access-1", "refresh-1");
    expect(getAccessToken()).toBe("access-1");
    expect(getRefreshToken()).toBe("refresh-1");
  });

  it("clears tokens", () => {
    setTokens("access-1", "refresh-1");
    clearTokens();
    expect(getAccessToken()).toBe("");
    expect(getRefreshToken()).toBe("");
  });
});
