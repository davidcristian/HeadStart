/** Persist API URL and JWT tokens in chrome.storage.local. */

import type { Session } from "./types";

const STORAGE_KEY = "headstart.session";

export async function loadSession(): Promise<Session | null> {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  const session = stored[STORAGE_KEY] as Session | undefined;
  if (!session?.apiBaseUrl || !session.accessToken || !session.refreshToken) {
    return null;
  }
  return {
    apiBaseUrl: session.apiBaseUrl.replace(/\/$/, ""),
    appBaseUrl: (session.appBaseUrl || defaultAppBaseUrl()).replace(/\/$/, ""),
    accessToken: session.accessToken,
    refreshToken: session.refreshToken,
  };
}

export async function saveSession(session: Session): Promise<void> {
  await chrome.storage.local.set({
    [STORAGE_KEY]: {
      ...session,
      apiBaseUrl: session.apiBaseUrl.replace(/\/$/, ""),
    },
  });
}

export async function clearSession(): Promise<void> {
  await chrome.storage.local.remove(STORAGE_KEY);
}

export function defaultApiBaseUrl(): string {
  return "http://localhost:8000";
}

export function defaultAppBaseUrl(): string {
  return "http://localhost:5173";
}
