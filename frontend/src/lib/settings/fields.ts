// What onboarding (W1–W8) and the Settings editors (S1) share: control bounds that mirror the API's
// validation, which settings field each server error belongs to, and small helpers over UserSettings.
// No calculations: totals such as "1,800 of 1,800 kcal a day planned" come from POST /settings/preview.
import type { MoneyScale } from "@/components/ui/Slider";
import { api, ApiError } from "@/lib/api/client";
import type { FieldError, FrequencyCap, SettingsPreview, UserSettings } from "@/lib/api/types";

type Bounds = { min: number; max: number; step: number };

// The same limits as backend/app/schemas/settings.py (FLOW_SPEC §6 for the steps).
export const PEOPLE: Bounds = { min: 1, max: 8, step: 1 };
export const DAILY_KCAL: Bounds = { min: 800, max: 6000, step: 50 };
export const PROTEIN_G: Bounds = { min: 0, max: 400, step: 5 };
export const SLOT_KCAL: Bounds = { min: 25, max: 3000, step: 25 };
// start to finish per cook day (V11, step 2b.9): up to 600, the backend's maximum
export const COOK_MINUTES: Bounds = { min: 0, max: 600, step: 15 };
export const PORK_MEALS: Bounds = { min: 0, max: 7, step: 1 };
/** Daily amount caps (M16): named units (scoops) in halves, grams and millilitres in 5s, counts in 1s. */
export const DAILY_CAP_NAMED: Bounds = { min: 0, max: 10, step: 0.5 };
export const DAILY_CAP_BASE: Bounds = { min: 0, max: 1000, step: 5 };
export const DAILY_CAP_COUNT: Bounds = { min: 0, max: 20, step: 1 };
export const CAP_MEALS: Bounds = { min: 0, max: 21, step: 1 };
export const BAND_KCAL: Bounds = { min: 0, max: 1000, step: 25 };
export const FRIDGE_DAYS: Bounds = { min: 0, max: 4, step: 1 }; // the FoodSafety.gov chart allows 4 at most
/** Separate-store trip threshold: $0–$20 in $1 steps. */
export const SPLIT_SCALE: MoneyScale = { min: 0, max: 2000, step: 100 };

export const WEEKDAYS = [
  { key: "mon", label: "Mon", long: "Monday" },
  { key: "tue", label: "Tue", long: "Tuesday" },
  { key: "wed", label: "Wed", long: "Wednesday" },
  { key: "thu", label: "Thu", long: "Thursday" },
  { key: "fri", label: "Fri", long: "Friday" },
  { key: "sat", label: "Sat", long: "Saturday" },
  { key: "sun", label: "Sun", long: "Sunday" },
] as const;

export const PORK_TAG = "pork";
const PORK_CAP: FrequencyCap = {
  label: "Pork as a meal component",
  target_type: "tag",
  target: PORK_TAG,
  max_meals_per_week: 1,
  never_favor: true,
};

export type DailyCap = NonNullable<UserSettings["daily_amount_caps"]>[number];

export function dailyCapBounds(unit: string): Bounds {
  if (unit === "g" || unit === "ml") return DAILY_CAP_BASE;
  return unit === "count" ? DAILY_CAP_COUNT : DAILY_CAP_NAMED;
}

/** "1 scoop", "2 scoops", "30 g": the setting's own numbers and unit, as written. */
export function capAmount(value: number, unit: string): string {
  if (unit === "g" || unit === "ml") return `${value} ${unit}`;
  if (unit === "count") return String(value);
  return `${value} ${unit}${value === 1 ? "" : "s"}`;
}

/** The Settings row before the API's summary line arrives. */
export function dailyCapsValue(settings: UserSettings): string {
  const caps = settings.daily_amount_caps ?? [];
  if (caps.length === 0) return "None";
  return caps.map((c) => `${c.label}: usually ${capAmount(c.usual, c.unit)} a day, at most ${capAmount(c.maximum, c.unit)}`).join(" · ");
}

export function porkCap(settings: UserSettings): FrequencyCap | null {
  return (settings.frequency_caps ?? []).find((c) => c.target_type === "tag" && c.target === PORK_TAG) ?? null;
}

/** The caps with the pork cap set to `meals` (added if you had none). */
export function withPorkMeals(settings: UserSettings, meals: number): FrequencyCap[] {
  const caps = settings.frequency_caps ?? [];
  if (!porkCap(settings)) return [...caps, { ...PORK_CAP, max_meals_per_week: meals }];
  return caps.map((c) => (c.target_type === "tag" && c.target === PORK_TAG ? { ...c, max_meals_per_week: meals } : c));
}

// ---------------- server errors -> the field (and screen) they belong to ----------------
// Field errors carry the field in loc[0]; whole-settings checks (loc []) are routed by their message.
const MESSAGE_FIELDS: [RegExp, string][] = [
  [/slot allocation/i, "slot_allocations"],
  [/cook day|cook_schedule|weekday/i, "cook_schedule"],
  [/store/i, "store_order"],
  [/frequency cap/i, "frequency_caps"],
  [/always.?have/i, "always_have"],
  [/secondary priority/i, "secondary_priority"],
  [/diet tag|must stay excluded/i, "excluded_diet_tags"],
];

export function fieldOf(error: FieldError): string {
  const first = error.loc[0];
  if (typeof first === "string" && first !== "body") return first;
  const second = error.loc[1];
  if (first === "body" && typeof second === "string") return second;
  return MESSAGE_FIELDS.find(([pattern]) => pattern.test(error.msg))?.[1] ?? "settings";
}

/** "Value error, slot allocations exceed…" -> "Slot allocations exceed…". */
export function cleanMessage(msg: string): string {
  const text = msg.replace(/^Value error,\s*/i, "").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export type FieldErrors = Record<string, string[]>;

export function errorsByField(errors: readonly FieldError[]): FieldErrors {
  const out: FieldErrors = {};
  for (const error of errors) {
    const field = fieldOf(error);
    const message = cleanMessage(error.msg);
    out[field] = [...(out[field] ?? []), ...(out[field]?.includes(message) ? [] : [message])];
  }
  return out;
}

/** The messages for some fields, in order (what one screen or editor shows). */
export function messagesFor(errors: FieldErrors, fields: readonly string[]): string[] {
  return fields.flatMap((f) => errors[f] ?? []);
}

/** POST /settings/preview: your saved settings with these fields replaced, checked but not saved. */
export function previewSettings(changes: Partial<UserSettings>): Promise<SettingsPreview> {
  return api<SettingsPreview>("/api/v1/settings/preview", { method: "POST", json: changes });
}

/** A 422 from PUT or PATCH /settings as field errors: Pydantic's `errors`, or the detail of a database check
 * ("unknown or inactive stores: …"). Anything else isn't a field problem: {}. */
export function errorsFromProblem(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || error.status !== 422) return {};
  if (error.errors.length) return errorsByField(error.errors);
  if (error.detail) return errorsByField(error.detail.split("; ").map((msg) => ({ loc: [], msg })));
  return {};
}
