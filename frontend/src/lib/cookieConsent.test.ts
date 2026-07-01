import { beforeEach, describe, expect, it } from "vitest";
import {
  acceptsOptionalCookies,
  clearCookieConsent,
  getCookieConsent,
  hasCookieConsent,
  setCookieConsent,
} from "./cookieConsent";

describe("cookieConsent", () => {
  beforeEach(() => {
    clearCookieConsent();
  });

  it("starts unset", () => {
    expect(getCookieConsent()).toBeNull();
    expect(hasCookieConsent()).toBe(false);
    expect(acceptsOptionalCookies()).toBe(false);
  });

  it("persists essential-only consent", () => {
    setCookieConsent("essential");
    expect(getCookieConsent()).toBe("essential");
    expect(hasCookieConsent()).toBe(true);
    expect(acceptsOptionalCookies()).toBe(false);
  });

  it("persists accept-all consent", () => {
    setCookieConsent("all");
    expect(getCookieConsent()).toBe("all");
    expect(acceptsOptionalCookies()).toBe(true);
  });

  it("clears stored consent", () => {
    setCookieConsent("all");
    clearCookieConsent();
    expect(getCookieConsent()).toBeNull();
  });
});
