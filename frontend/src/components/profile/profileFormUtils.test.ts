import { describe, expect, it } from "vitest";
import { parseOptionalInt, updateRow } from "./profileFormUtils";

describe("parseOptionalInt", () => {
  it("returns null for blank input", () => {
    expect(parseOptionalInt("")).toBeNull();
    expect(parseOptionalInt("   ")).toBeNull();
  });

  it("parses a finite number", () => {
    expect(parseOptionalInt(" 42 ")).toBe(42);
  });

  it("returns null for non-numeric input", () => {
    expect(parseOptionalInt("abc")).toBeNull();
  });
});

describe("updateRow", () => {
  it("patches only the row at the given index", () => {
    const rows = [{ n: 1 }, { n: 2 }, { n: 3 }];
    const next = updateRow(rows, 1, { n: 20 });
    expect(next).toEqual([{ n: 1 }, { n: 20 }, { n: 3 }]);
    expect(next[0]).toBe(rows[0]);
    expect(next[1]).not.toBe(rows[1]);
  });
});
