import { describe, expect, it } from "vitest";
import { parseOptionalInt, updateRow } from "./profileFormUtils";

describe("parseOptionalInt", () => {
  it("returns null for blank input", () => {
    expect(parseOptionalInt("")).toBeNull();
    expect(parseOptionalInt("   ")).toBeNull();
  });

  it("parses a finite integer", () => {
    expect(parseOptionalInt(" 42 ")).toBe(42);
  });

  it("returns null for non-numeric input", () => {
    expect(parseOptionalInt("abc")).toBeNull();
  });

  it("truncates decimals to an integer (FRO-27)", () => {
    expect(parseOptionalInt("3.5")).toBe(3);
    expect(parseOptionalInt("2024.9")).toBe(2024);
    expect(parseOptionalInt("-2.7")).toBe(-2);
  });

  it("clamps to optional min/max (FRO-27)", () => {
    expect(parseOptionalInt("-2", 1, 12)).toBe(1);
    expect(parseOptionalInt("13", 1, 12)).toBe(12);
    expect(parseOptionalInt("3.5", 1, 12)).toBe(3);
    expect(parseOptionalInt("1899", 1900, 2100)).toBe(1900);
    expect(parseOptionalInt("2101", 1900, 2100)).toBe(2100);
    expect(parseOptionalInt("2020.4", 1900, 2100)).toBe(2020);
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
