/** Thin typed fetch wrapper. All network access goes through here.
 *
 * Every request carries the in-memory access token plus the httpOnly refresh
 * cookie (`credentials: "include"`). On a 401 we transparently try the
 * cookie-based refresh once; if that fails the session is cleared and a
 * registered handler (the AuthContext) is notified so the UI can redirect to
 * login.
 */

import { clearAccessToken, getAccessToken, getApiBaseUrl, setAccessToken } from "../lib/settings";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

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
    credentials: "include",
  });
}

/** Exchange the httpOnly refresh cookie for a fresh access token. */
export async function refreshSession(): Promise<boolean> {
  const resp = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!resp.ok) return false;
  const data = (await resp.json()) as { access_token: string };
  setAccessToken(data.access_token);
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

/** Multipart upload (e.g. resume file). Does not set Content-Type — the browser adds the boundary. */
export async function requestForm<T>(
  path: string,
  options: RequestOptions & { body: FormData },
): Promise<T> {
  const { method = "POST", body, skipAuth = false } = options;

  async function doFetch(token: string): Promise<Response> {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers,
      body,
      credentials: "include",
    });
  }

  if (skipAuth) {
    return parse<T>(await doFetch(""));
  }

  let resp = await doFetch(getAccessToken());
  if (resp.status === 401) {
    const refreshed = await refreshSession();
    if (refreshed) {
      resp = await doFetch(getAccessToken());
    }
    if (resp.status === 401) {
      clearAccessToken();
      onUnauthorized?.();
    }
  }
  return parse<T>(resp);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false } = options;

  if (skipAuth) {
    return parse<T>(await rawFetch(path, method, body, ""));
  }

  let resp = await rawFetch(path, method, body, getAccessToken());
  if (resp.status === 401) {
    const refreshed = await refreshSession();
    if (refreshed) {
      resp = await rawFetch(path, method, body, getAccessToken());
    }
    if (resp.status === 401) {
      clearAccessToken();
      onUnauthorized?.();
    }
  }
  return parse<T>(resp);
}

/** Authenticated binary download (e.g. stored PDF artifacts). */
export async function requestBlob(path: string): Promise<Blob> {
  async function doFetch(token: string): Promise<Response> {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${getApiBaseUrl()}${path}`, {
      method: "GET",
      headers,
      credentials: "include",
    });
  }

  let resp = await doFetch(getAccessToken());
  if (resp.status === 401) {
    const refreshed = await refreshSession();
    if (refreshed) {
      resp = await doFetch(getAccessToken());
    }
    if (resp.status === 401) {
      clearAccessToken();
      onUnauthorized?.();
    }
  }
  if (!resp.ok) {
    const text = await resp.text();
    let detail = resp.statusText;
    try {
      const data = text ? JSON.parse(text) : undefined;
      detail = (data && (data.detail as string)) || detail;
    } catch {
      detail = text || detail;
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.blob();
}
