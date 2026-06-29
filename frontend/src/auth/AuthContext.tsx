/** Authentication state: current user + login/register/logout actions.
 *
 * The access token lives only in memory (see lib/settings) and the refresh
 * token is an httpOnly cookie. On load we exchange that cookie for a fresh
 * access token; this context tracks the resolved user and reacts to
 * unrecoverable 401s reported by the API client.
 */

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
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    void api.logout().catch(() => undefined);
    clearAccessToken();
    setUser(null);
  }, []);

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
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    setAccessToken(tokens.access_token);
    setUser(await api.me());
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await api.register(email, password);
      await login(email, password);
    },
    [login],
  );

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
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
