/** Runtime-configurable connection settings + JWT storage, in localStorage.
 *
 * The API base URL falls back to the build-time VITE_API_BASE_URL, then to a
 * sensible local default. Access/refresh tokens are issued by `/auth/login`
 * and `/auth/register` and are attached to every request by the API client.
 */

const BASE_URL_KEY = "jobnotifier.apiBaseUrl";
const ACCESS_TOKEN_KEY = "jobnotifier.accessToken";
const REFRESH_TOKEN_KEY = "jobnotifier.refreshToken";

const DEFAULT_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export function getApiBaseUrl(): string {
  return (localStorage.getItem(BASE_URL_KEY) || DEFAULT_BASE_URL).replace(/\/$/, "");
}

export function setApiBaseUrl(url: string): void {
  localStorage.setItem(BASE_URL_KEY, url.trim());
}

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

export function getRefreshToken(): string {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || "";
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}
