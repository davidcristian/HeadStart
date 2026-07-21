import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearAccessToken, getAccessToken, setAccessToken } from "../lib/settings";
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
const apiRegister = vi.fn(async (_email: string, _password: string) => ({
  message: "If this email is available, we created an account and sent a verification link.",
}));
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

let queryClient: QueryClient;
let clearSpy: ReturnType<typeof vi.spyOn>;

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
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
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    clearSpy = vi.spyOn(queryClient, "clear");
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

  it("registers a new account without signing in", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.register("x@example.test", "password123");
    });

    expect(apiRegister).toHaveBeenCalledWith("x@example.test", "password123");
    expect(apiLogin).not.toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBe("");
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
    clearSpy.mockClear();

    act(() => result.current.logout());
    await waitFor(() => expect(result.current.user).toBeNull());
    expect(apiLogout).toHaveBeenCalled();
    expect(clearSpy).toHaveBeenCalled();
  });

  it("registers an unauthorized handler that clears the user and cache on a hard 401", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("x@example.test", "password123");
    });
    expect(result.current.user?.email).toBe("x@example.test");
    clearSpy.mockClear();

    const handler = setUnauthorizedHandler.mock.calls
      .map((c) => c[0])
      .find((arg): arg is () => void => typeof arg === "function");
    expect(handler).toBeDefined();

    act(() => handler!());
    await waitFor(() => expect(result.current.user).toBeNull());
    expect(clearSpy).toHaveBeenCalled();
  });

  it("removes the unauthorized handler on unmount", async () => {
    const { unmount } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(setUnauthorizedHandler).toHaveBeenCalled());
    setUnauthorizedHandler.mockClear();

    unmount();
    expect(setUnauthorizedHandler).toHaveBeenCalledWith(null);
  });

  it("drops a bootstrap result that lands after the provider unmounts", async () => {
    refreshSession.mockResolvedValue(true);
    let resolveMe!: (value: typeof user) => void;
    apiMe.mockReturnValue(
      new Promise<typeof user>((resolve) => {
        resolveMe = resolve;
      }),
    );
    const { result, unmount } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(apiMe).toHaveBeenCalled());

    unmount();
    await act(async () => {
      resolveMe(user);
    });

    // The cleanup flag short-circuits both the setUser and the setLoading call.
    expect(result.current.user).toBeNull();
    expect(result.current.loading).toBe(true);
  });

  it("drops a bootstrap failure that lands after the provider unmounts", async () => {
    setAccessToken("stale-token");
    let rejectRefresh!: (reason: Error) => void;
    refreshSession.mockReturnValue(
      new Promise<boolean>((_resolve, reject) => {
        rejectRefresh = reject;
      }),
    );
    const { unmount } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(refreshSession).toHaveBeenCalled());

    unmount();
    await act(async () => {
      rejectRefresh(new Error("network"));
    });

    // An unmounted provider must not clear the token a newer provider may own.
    expect(getAccessToken()).toBe("stale-token");
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
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Consumer />
        </AuthProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("x@example.test")).toBeInTheDocument();
  });
});
