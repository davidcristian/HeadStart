/** Runtime connection settings + in-memory access-token storage.
 *
 * The API base URL is persisted in localStorage. The access token is held only
 * in memory (a module variable) — never in localStorage/sessionStorage — so it
 * is not exposed to XSS or readable across tabs. The long-lived refresh token is
 * an httpOnly cookie owned by the backend and is never visible to JavaScript; on
 * a fresh load the app exchanges that cookie for a new access token.
 */

const BASE_URL_KEY = "headstart.apiBaseUrl";

const DEFAULT_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

let accessToken = "";

export function getApiBaseUrl(): string {
  return (localStorage.getItem(BASE_URL_KEY) || DEFAULT_BASE_URL).replace(/\/$/, "");
}

export function setApiBaseUrl(url: string): void {
  localStorage.setItem(BASE_URL_KEY, url.trim());
}

export function getAccessToken(): string {
  return accessToken;
}

export function setAccessToken(token: string): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = "";
}
