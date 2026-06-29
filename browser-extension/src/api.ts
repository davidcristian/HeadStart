/** Minimal HeadStart API client for the browser extension popup. */

import type { Search, Session, Source, SourceDetectResult, TokenResponse } from "./types";
import { ApiError } from "./types";

async function parse<T>(resp: Response): Promise<T> {
  if (resp.status === 204) {
    return undefined as T;
  }
  const text = await resp.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!resp.ok) {
    const detail = (data && (data.detail as string)) || resp.statusText;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

async function rawFetch(
  session: Session,
  path: string,
  method: string,
  body: unknown,
  token: string,
): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(`${session.apiBaseUrl}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function tryRefresh(session: Session): Promise<Session | null> {
  const resp = await fetch(`${session.apiBaseUrl}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refreshToken }),
  });
  if (!resp.ok) {
    return null;
  }
  const data = (await resp.json()) as TokenResponse;
  return {
    ...session,
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
  };
}

async function request<T>(
  session: Session,
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<{ data: T; session: Session }> {
  const method = options.method ?? "GET";
  let active = session;
  let resp = await rawFetch(active, path, method, options.body, active.accessToken);
  if (resp.status === 401) {
    const refreshed = await tryRefresh(active);
    if (refreshed) {
      active = refreshed;
      resp = await rawFetch(active, path, method, options.body, active.accessToken);
    }
  }
  const data = await parse<T>(resp);
  return { data, session: active };
}

export async function login(
  apiBaseUrl: string,
  email: string,
  password: string,
  appBaseUrl: string,
): Promise<Session> {
  const base = apiBaseUrl.replace(/\/$/, "");
  const resp = await fetch(`${base}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await parse<TokenResponse>(resp);
  return {
    apiBaseUrl: base,
    appBaseUrl: appBaseUrl.replace(/\/$/, ""),
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
  };
}

export async function detectSource(
  session: Session,
  url: string,
  pageTitle: string | null,
): Promise<{ data: SourceDetectResult; session: Session }> {
  return request<SourceDetectResult>(session, "/api/v1/sources/detect", {
    method: "POST",
    body: { url, page_title: pageTitle },
  });
}

export async function createSource(
  session: Session,
  payload: {
    name: string;
    adapter_key: string;
    base_url: string;
    default_config: Record<string, unknown>;
    enabled: boolean;
  },
): Promise<{ data: Source; session: Session }> {
  return request<Source>(session, "/api/v1/sources", {
    method: "POST",
    body: payload,
  });
}

export async function createSearch(
  session: Session,
  payload: {
    name: string;
    source_id: number;
    query_url: string;
    enabled: boolean;
    interval_seconds: number;
  },
): Promise<{ data: Search; session: Session }> {
  return request<Search>(session, "/api/v1/searches", {
    method: "POST",
    body: {
      ...payload,
      target_id: null,
      filters: {},
      config: {},
      notification_mode: "immediate",
      digest_interval_seconds: 3600,
    },
  });
}
