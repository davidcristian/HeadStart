import { describe, expect, it } from "vitest";
import { safeHref } from "./safeHref";

describe("safeHref", () => {
  it("allows http and https URLs", () => {
    expect(safeHref("https://jobs.example.com/1")).toBe("https://jobs.example.com/1");
    expect(safeHref("http://jobs.example.com/1")).toBe("http://jobs.example.com/1");
  });

  it("trims whitespace before validating", () => {
    expect(safeHref("  https://jobs.example.com/1  ")).toBe("https://jobs.example.com/1");
  });

  it("rejects javascript: and other non-http schemes", () => {
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref("JAVASCRIPT:alert(1)")).toBeNull();
    expect(safeHref("data:text/html,<script>alert(1)</script>")).toBeNull();
    expect(safeHref("mailto:user@example.com")).toBeNull();
    expect(safeHref("vbscript:msgbox(1)")).toBeNull();
  });

  it("rejects empty, blank, relative, and malformed values", () => {
    expect(safeHref(null)).toBeNull();
    expect(safeHref(undefined)).toBeNull();
    expect(safeHref("")).toBeNull();
    expect(safeHref("   ")).toBeNull();
    expect(safeHref("/jobs/1")).toBeNull();
    expect(safeHref("not a url")).toBeNull();
  });
});
