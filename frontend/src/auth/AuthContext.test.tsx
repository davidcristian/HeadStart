import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearAccessToken, getAccessToken } from "../lib/settings";
import { AuthProvider, useAuth } from "./AuthContext";

const user = {
  id: 1,
  email: "x@example.test",
  is_admin: true,
  is_active: true,
  plan: "team" as const,
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

vi.mock("../api", () => ({
  api: {
    login: vi.fn(async () => ({ access_token: "access-token", token_type: "bearer" })),
    register: vi.fn(async () => user),
    logout: vi.fn(async () => ({ message: "Logged out." })),
    me: vi.fn(async () => user),
  },
}));

// The cookie-based refresh hits the network; stub it so bootstrap resolves to an
// unauthenticated state by default (no valid refresh cookie in tests).
const { refreshSession } = vi.hoisted(() => ({ refreshSession: vi.fn(async () => false) }));
vi.mock("../api/client", () => ({
  refreshSession,
  setUnauthorizedHandler: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("AuthContext", () => {
  beforeEach(() => {
    clearAccessToken();
    refreshSession.mockResolvedValue(false);
  });

  it("starts unauthenticated when the refresh cookie is absent", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
  });

  it("logs in, stores the access token in memory, and exposes the user", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("x@example.test", "password123");
    });

    expect(getAccessToken()).toBe("access-token");
    expect(result.current.user?.email).toBe("x@example.test");
  });

  it("logout clears the session", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.login("x@example.test", "password123");
    });

    act(() => result.current.logout());

    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBe("");
  });
});
