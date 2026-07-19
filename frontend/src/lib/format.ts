/** Small date/format helpers for the UI. */

/** Display locale for absolute timestamps (deterministic; DE audience). */
export const APP_DATE_LOCALE = "de-DE";

/** Display timezone for absolute timestamps (explicit; not the browser zone). */
export const APP_TIME_ZONE = "Europe/Berlin";

const dateTimeFormatter = new Intl.DateTimeFormat(APP_DATE_LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: APP_TIME_ZONE,
  timeZoneName: "short",
});

const dateFormatter = new Intl.DateTimeFormat(APP_DATE_LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: APP_TIME_ZONE,
});

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

/** Absolute date+time in APP_DATE_LOCALE / APP_TIME_ZONE (includes zone abbr). */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

/** Absolute calendar date in APP_DATE_LOCALE / APP_TIME_ZONE. */
export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}
