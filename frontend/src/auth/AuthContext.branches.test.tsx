import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearAccessToken, getAccessToken } from "../lib/settings";
import { AuthProvider, useAuth } from "./AuthContext";

const user = {
  id: 1,
  email: "x@example.test",
  is_admin: true,
  is_active: true,
  plan: "pro" as const,
  onboarding_completed_at: "2026-06-28T00:00:00Z",
  email_verified_at: "2026-06-28T00:00:00Z",
  created_at: "2026-06-28T00:00:00Z",
};

const apiLogin = vi.fn(async (_email: string, _password: string) => ({
  access_token: "access-token",
  token_type: "bearer",
}));
const apiRegister = vi.fn(async (_email: string, _password: string) => user);
const apiLogout = vi.fn(async () => ({ message: "Logged out." }));
const apiMe = vi.fn(async () => user);

vi.mock("../api", () => ({
  api: {
    login: (email: string, password: string) => apiLogin(email, password),
    register: (email: string, password: string) => apiRegister(email, password),
    logout: () => apiLogout(),
    me: () => apiMe(),
  },
}));

const { refreshSession, setUnauthorizedHandler } = vi.hoisted(() => ({
  refreshSession: vi.fn(async () => false),
  setUnauthorizedHandler: vi.fn(),
}));
vi.mock("../api/client", () => ({ refreshSession, setUnauthorizedHandler }));

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("AuthContext (branches)", () => {
  beforeEach(() => {
    clearAccessToken();
    refreshSession.mockReset();
    refreshSession.mockResolvedValue(false);
    setUnauthorizedHandler.mockReset();
    apiLogin.mockClear();
    apiRegister.mockClear();
    apiLogout.mockClear();
    apiMe.mockClear();
    apiMe.mockResolvedValue(user);
  });

  it("loads the current user when a valid refresh cookie is present", async () => {
    refreshSession.mockResolvedValue(true);
    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.user?.email).toBe("x@example.test"));
    expect(result.current.loading).toBe(false);
    expect(apiMe).toHaveBeenCalled();
  });

  it("clears the access token when bootstrap fails", async () => {
    refreshSession.mockRejectedValue(new Error("network"));
    const { result } = renderHook(() => useAuth(), { wrapper });

    // Bootstrap swallows the error; the user stays null and no token is retained.
    await waitFor(() => expect(refreshSession).toHaveBeenCalled());
    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBe("");
  });

  it("registers a new account and then logs in", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.register("x@example.test", "password123");
    });

    expect(apiRegister).toHaveBeenCalledWith("x@example.test", "password123");
    expect(apiLogin).toHaveBeenCalledWith("x@example.test", "password123");
    expect(result.current.user?.email).toBe("x@example.test");
    expect(getAccessToken()).toBe("access-token");
  });

  it("refreshUser re-fetches the current user", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    apiMe.mockResolvedValueOnce({ ...user, email: "refreshed@example.test" });
    await act(async () => {
      await result.current.refreshUser();
    });

    expect(result.current.user?.email).toBe("refreshed@example.test");
  });

  it("logout swallows a rejected api.logout call", async () => {
    apiLogout.mockRejectedValueOnce(new Error("offline"));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("x@example.test", "password123");
    });

    act(() => result.current.logout());
    await waitFor(() => expect(result.current.user).toBeNull());
    expect(apiLogout).toHaveBeenCalled();
  });

  it("registers an unauthorized handler that clears the user on a hard 401", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("x@example.test", "password123");
    });
    expect(result.current.user?.email).toBe("x@example.test");

    const handler = setUnauthorizedHandler.mock.calls
      .map((c) => c[0])
      .find((arg): arg is () => void => typeof arg === "function");
    expect(handler).toBeDefined();

    act(() => handler!());
    await waitFor(() => expect(result.current.user).toBeNull());
  });

  it("removes the unauthorized handler on unmount", async () => {
    const { unmount } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(setUnauthorizedHandler).toHaveBeenCalled());
    setUnauthorizedHandler.mockClear();

    unmount();
    expect(setUnauthorizedHandler).toHaveBeenCalledWith(null);
  });

  it("throws when useAuth is used outside an AuthProvider", () => {
    function Consumer() {
      useAuth();
      return null;
    }
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Consumer />)).toThrow("useAuth must be used within an AuthProvider");
    spy.mockRestore();
  });

  it("exposes the resolved user through consuming components", async () => {
    refreshSession.mockResolvedValue(true);
    function Consumer() {
      const { user: current, loading } = useAuth();
      return <div>{loading ? "loading" : (current?.email ?? "anon")}</div>;
    }
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    expect(await screen.findByText("x@example.test")).toBeInTheDocument();
  });
});
