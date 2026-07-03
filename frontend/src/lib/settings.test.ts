import { beforeEach, describe, expect, it } from "vitest";
import {
  clearAccessToken,
  getAccessToken,
  getApiBaseUrl,
  setAccessToken,
  setApiBaseUrl,
} from "./settings";

describe("settings", () => {
  beforeEach(() => {
    localStorage.clear();
    clearAccessToken();
  });

  it("strips trailing slashes from the base URL", () => {
    setApiBaseUrl("http://example.test/");
    expect(getApiBaseUrl()).toBe("http://example.test");
  });

  it("holds the access token in memory", () => {
    expect(getAccessToken()).toBe("");
    setAccessToken("access-1");
    expect(getAccessToken()).toBe("access-1");
  });

  it("clears the access token", () => {
    setAccessToken("access-1");
    clearAccessToken();
    expect(getAccessToken()).toBe("");
  });

  it("never persists the access token to localStorage", () => {
    setAccessToken("secret-token");
    expect(localStorage.getItem("headstart.accessToken")).toBeNull();
    expect(JSON.stringify(localStorage)).not.toContain("secret-token");
  });
});
