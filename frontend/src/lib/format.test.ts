import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatDateTime, formatRelativeTime } from "./format";

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
  it("delegates to Date.toLocaleString", () => {
    const iso = "2026-07-01T12:00:00Z";
    expect(formatDateTime(iso)).toBe(new Date(iso).toLocaleString());
  });
});
