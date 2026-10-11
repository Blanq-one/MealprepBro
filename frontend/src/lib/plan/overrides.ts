// This plan's day choices (PlanRequest.day_overrides): the "no plan fits" fixes for time and mood (2b.3b
// approval, P4) change one day's hands-on minutes or mood for this plan only, never your settings.
import type { PlanRequestBody } from "@/lib/api/types";
import { parseDay, toIso } from "@/lib/format/dates";

export type DayOverride = NonNullable<PlanRequestBody["day_overrides"]>[number];

/** The day choices with these changes applied (a later change to the same day wins, field by field). */
export function withOverrides(overrides: DayOverride[], changes: DayOverride[]): DayOverride[] {
  let out = overrides;
  for (const change of changes) {
    const same = out.find((o) => o.day === change.day);
    out = [...out.filter((o) => o.day !== change.day), { ...same, ...change }];
  }
  return out;
}

/** The seven dates of the week to plan, for a change that applies to every day. */
export function weekDays(weekStart: string): string[] {
  const start = parseDay(weekStart);
  return Array.from({ length: 7 }, (_, i) => toIso(new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)));
}
