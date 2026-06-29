/** Render helper that wraps a UI tree in a fresh React Query client.
 *
 * Each call gets its own QueryClient with retries disabled so tests stay fast
 * and isolated (no cache bleed between cases, no retry backoff on errors).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}
