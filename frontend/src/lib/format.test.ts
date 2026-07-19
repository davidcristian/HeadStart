import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatDate, formatDateTime, formatRelativeTime } from "./format";

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-01T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows 'just now' under a minute", () => {
    expect(formatRelativeTime("2026-07-01T11:59:30Z")).toBe("just now");
  });

  it("shows minutes under an hour", () => {
    expect(formatRelativeTime("2026-07-01T11:30:00Z")).toBe("30m ago");
  });

  it("shows hours under 48h", () => {
    expect(formatRelativeTime("2026-07-01T06:00:00Z")).toBe("6h ago");
  });

  it("shows days once past 48h", () => {
    expect(formatRelativeTime("2026-06-28T12:00:00Z")).toBe("3d ago");
  });
});

describe("formatDateTime", () => {
  it("formats with fixed de-DE locale and Europe/Berlin zone", () => {
    // 12:00 UTC in July is 14:00 MESZ (CEST).
    expect(formatDateTime("2026-07-01T12:00:00Z")).toBe("01.07.2026, 14:00 MESZ");
  });

  it("uses winter offset (MEZ) when Berlin is on standard time", () => {
    expect(formatDateTime("2026-01-15T12:00:00Z")).toBe("15.01.2026, 13:00 MEZ");
  });
});

describe("formatDate", () => {
  it("formats a calendar date in de-DE / Europe/Berlin", () => {
    // Late-evening UTC can still be the next calendar day in Berlin.
    expect(formatDate("2026-07-01T22:30:00Z")).toBe("02.07.2026");
  });
});
