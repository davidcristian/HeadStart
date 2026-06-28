/** Thin typed fetch wrapper. All network access goes through here.
 *
 * Every request carries the access token. On a 401 we transparently try the
 * refresh token once; if that fails the session is cleared and a registered
 * handler (the AuthContext) is notified so the UI can redirect to login.
 */

import {
  clearTokens,
  getAccessToken,
  getApiBaseUrl,
  getRefreshToken,
  setTokens,
} from "../lib/settings";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: Method;
  body?: unknown;
  /** Skip the access token + refresh dance (used by the auth endpoints). */
  skipAuth?: boolean;
}

let onUnauthorized: (() => void) | null = null;

/** Register a callback invoked when the session can no longer be refreshed. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function rawFetch(
  path: string,
  method: Method,
  body: unknown,
  token: string,
): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${getApiBaseUrl()}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  const resp = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!resp.ok) return false;
  const data = (await resp.json()) as { access_token: string; refresh_token: string };
  setTokens(data.access_token, data.refresh_token);
  return true;
}

async function parse<T>(resp: Response): Promise<T> {
  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!resp.ok) {
    const detail = (data && (data.detail as string)) || resp.statusText;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false } = options;

  if (skipAuth) {
    return parse<T>(await rawFetch(path, method, body, ""));
  }

  let resp = await rawFetch(path, method, body, getAccessToken());
  if (resp.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      resp = await rawFetch(path, method, body, getAccessToken());
    }
    if (resp.status === 401) {
      clearTokens();
      onUnauthorized?.();
    }
  }
  return parse<T>(resp);
}
