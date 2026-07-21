/** Authentication state: current user + login/register/logout actions.
 *
 * The access token lives only in memory (see lib/settings) and the refresh
 * token is an httpOnly cookie. On load we exchange that cookie for a fresh
 * access token; this context tracks the resolved user and reacts to
 * unrecoverable 401s reported by the API client.
 */

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import { refreshSession, setUnauthorizedHandler } from "../api/client";
import { clearAccessToken, setAccessToken } from "../lib/settings";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    void api.logout().catch(() => undefined);
    clearAccessToken();
    setUser(null);
    // Drop cached queries so the next session cannot read the previous user's PII.
    queryClient.clear();
  }, [queryClient]);

  // Resolve the session on first load by exchanging the refresh cookie for an
  // access token, then loading the current user.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const refreshed = await refreshSession();
        if (!refreshed) return;
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) clearAccessToken();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // The API client calls this when a refresh fails.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      queryClient.clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.login(email, password);
      setAccessToken(tokens.access_token);
      // Clear before loading the new user so a shared-browser re-login cannot
      // briefly serve the previous account's cached sources/jobs/profile.
      queryClient.clear();
      setUser(await api.me());
    },
    [queryClient],
  );

  const register = useCallback(async (email: string, password: string) => {
    // Do not auto-login: duplicate emails also return success so existence
    // cannot be inferred from a follow-up login failure.
    await api.register(email, password);
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await api.me();
    setUser(me);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refreshUser }),
    [user, loading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
