/** Narrow `T | undefined` for tests under `noUncheckedIndexedAccess` (FRO-42). */
export function must<T>(value: T | null | undefined, label = "value"): T {
  if (value == null) {
    throw new Error(`expected ${label} to be defined`);
  }
  return value;
}
