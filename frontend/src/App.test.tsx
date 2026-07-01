import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { CookieConsentProvider } from "./components/CookieConsentContext";

vi.mock("./api", () => ({
  api: {
    health: vi.fn(async () => ({ version: "test", environment: "test" })),
    logout: vi.fn(async () => ({ message: "ok" })),
    me: vi.fn(async () => null),
  },
}));

// Bootstrap finds no valid refresh cookie, so the app loads unauthenticated.
vi.mock("./api/client", () => ({
  refreshSession: vi.fn(async () => false),
  setUnauthorizedHandler: vi.fn(),
}));

function renderAt(path: string): ReturnType<typeof render> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <CookieConsentProvider>
            <App />
          </CookieConsentProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(ui);
}

describe("App routing", () => {
  it("serves the public landing page at /", () => {
    renderAt("/");
    expect(
      screen.getByRole("heading", { name: "See new roles before the crowd." }),
    ).toBeInTheDocument();
  });

  it("serves legal pages without authentication", () => {
    renderAt("/privacy");
    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();

    renderAt("/impressum");
    expect(screen.getByRole("heading", { name: "Impressum" })).toBeInTheDocument();

    renderAt("/subprocessors");
    expect(screen.getByRole("heading", { name: "Subprocessors" })).toBeInTheDocument();
  });

  it("serves the pricing page without authentication", () => {
    renderAt("/pricing");
    expect(screen.getByRole("heading", { name: "Pay for signal, not noise." })).toBeInTheDocument();
  });

  it("redirects an unauthenticated visitor from /app to the login screen", async () => {
    renderAt("/app");
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Sign in to HeadStart" })).toBeInTheDocument(),
    );
  });

  it("redirects unknown public routes back to the landing page", async () => {
    renderAt("/totally-unknown");
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "See new roles before the crowd." }),
      ).toBeInTheDocument(),
    );
  });

  it("redirects legacy app paths under /app (which then gate on auth)", async () => {
    renderAt("/jobs");
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Sign in to HeadStart" })).toBeInTheDocument(),
    );
  });
});
