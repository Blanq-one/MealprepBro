// Calendar helpers for display and defaults. Dates from the API are "YYYY-MM-DD" in your timezone.

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map((p) => Number.parseInt(p, 10));
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export function toIso(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

/** "2026-10-12" -> "Mon Oct 12". */
export function dayLabel(iso: string): string {
  const date = parseDay(iso);
  return `${WEEKDAYS[date.getDay()]} ${MONTHS[date.getMonth()]} ${date.getDate()}`;
}

/** "2026-10-12" -> "Oct 12". */
export function shortDate(iso: string): string {
  const date = parseDay(iso);
  return `${MONTHS[date.getMonth()]} ${date.getDate()}`;
}

/** The Monday after today (today, if it is a Monday): the default week to plan. */
export function nextMonday(today: Date = new Date()): string {
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const ahead = (8 - date.getDay()) % 7;
  date.setDate(date.getDate() + ahead);
  return toIso(date);
}

/** Whole days from today to the date (negative = past). */
export function daysUntil(iso: string, today: Date = new Date()): number {
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  return Math.round((parseDay(iso).getTime() - start) / 86_400_000);
}

export function todayIso(): string {
  return toIso(new Date());
}

/** "just now", "3 min ago", "2 h ago", or a date. */
export function agoLabel(timestamp: number, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - timestamp) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)} h ago`;
  return dayLabel(toIso(new Date(timestamp)));
}
