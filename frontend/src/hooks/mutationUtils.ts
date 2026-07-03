import type { QueryClient } from "@tanstack/react-query";

export function invalidate(qc: QueryClient, key: readonly unknown[]) {
  return qc.invalidateQueries({ queryKey: key });
}
