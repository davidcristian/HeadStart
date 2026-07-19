/** Shared helpers for repeatable profile form rows. */

/** Parse a trimmed integer; empty/non-numeric → null. Optional min/max clamp (FRO-27). */
export function parseOptionalInt(value: string, min?: number, max?: number): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return null;
  let n = Math.trunc(parsed);
  if (min !== undefined) n = Math.max(min, n);
  if (max !== undefined) n = Math.min(max, n);
  return n;
}

export function updateRow<T>(rows: T[], index: number, patch: Partial<T>): T[] {
  return rows.map((row, i) => (i === index ? { ...row, ...patch } : row));
}
