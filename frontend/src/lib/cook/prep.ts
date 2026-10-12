// The meal-prep answers (FLOW_SPEC §7 C1, C1b, C2, C3, C3b): kept as a draft on this device while you answer,
// then sent as CookAnswers to POST /cook/meal-prep. Nothing here computes a nutrition, amount or money number:
// the server resolves the days, meals, cook days and limits (app/cook/prep.py). The days below are calendar
// days for the chips, and the minutes come straight from your settings.
import type { CookAnswers, CookDay, MealSlot, RecipeMood, UserSettings } from "@/lib/api/types";
import { parseDay, toIso } from "@/lib/format/dates";
import type { GoalKey } from "@/lib/format/icons";

import { type DraftExtra, GOAL_TILES, QUICK_DEFAULT_MINUTES } from "./answers";

export type CookStyle = "big_day" | "sessions" | "same_dish" | "mix";
/** C1's tiles: three presets and "Something else". */
export type AmountPreset = "five_lunches" | "lunch_dinner_5" | "usual_week" | "custom";
/** "today", "tomorrow" (they move with the calendar, so Same as last time still works next week), or a date. */
export type DayChoice = "today" | "tomorrow" | string;

export type PrepDraft = {
  preset: AmountPreset | null; // null = not picked yet
  shape: "portions" | "days"; // Something else: by portions or by days
  slot: MealSlot | null; // by portions: the meal
  portions: number; // by portions: that meal on this many days in a row
  dayCount: number; // by days
  slots: MealSlot[]; // by days: the meals
  start: DayChoice;
  extraToFreeze: number;
  style: CookStyle | null; // null = not picked yet
  cookDay: DayChoice | null; // one big cook day, same dish: the day (null = the start day)
  cookMinutes: number | null; // ... and its minutes, start to finish (null = that day's usual)
  sessions: { day: string; minutes: number }[]; // a few sessions: the days (dates) and their minutes
  people: number | null;
  goals: GoalKey[];
  quickMinutes: number | null;
  mood: RecipeMood | null;
  off: number[];
  extras: DraftExtra[];
  shopping: "use_what_i_have" | "make_a_list" | null;
  budgetCents: number | null; // a shopping list's limit, or "Use what I have"'s top-up; null = none
};

export const PREP_DRAFT_KEY = "mealbro.cook.prep";
export const MAX_PREP_DAYS = 14; // meal prep plans up to 14 days (app/cook/prep.py MAX_DAYS)
export const MAX_EXTRA_FREEZE = 20;
export const PREP_MINUTES = { min: 0, max: 600, step: 15 } as const; // start to finish (V11), up to 600
export const PREP_STEPS = ["amount", "when", "goals", "have", "shop"] as const;
export type PrepStep = (typeof PREP_STEPS)[number];

export function emptyPrepDraft(): PrepDraft {
  return {
    preset: null,
    shape: "portions",
    slot: null,
    portions: 5,
    dayCount: 5,
    slots: [],
    start: "today",
    extraToFreeze: 0,
    style: null,
    cookDay: null,
    cookMinutes: null,
    sessions: [],
    people: null,
    goals: [],
    quickMinutes: null,
    mood: null,
    off: [],
    extras: [],
    shopping: null,
    budgetCents: null,
  };
}

/** The meals and days a draft asks for (a preset, or Something else). */
export function amountOf(draft: PrepDraft, settings: UserSettings | null): { shape: "portions" | "days"; slot: MealSlot | null; portions: number; dayCount: number; slots: MealSlot[] } {
  switch (draft.preset) {
    case "five_lunches":
      return { shape: "portions", slot: "lunch", portions: 5, dayCount: 5, slots: ["lunch"] };
    case "lunch_dinner_5":
      return { shape: "days", slot: null, portions: 5, dayCount: 5, slots: ["lunch", "dinner"] };
    case "usual_week":
      return { shape: "days", slot: null, portions: 7, dayCount: 7, slots: (settings?.slot_allocations ?? []).map((a) => a.slot) };
    default:
      if (draft.shape === "portions") return { shape: "portions", slot: draft.slot, portions: draft.portions, dayCount: draft.portions, slots: draft.slot ? [draft.slot] : [] };
      return { shape: "days", slot: null, portions: draft.dayCount, dayCount: draft.dayCount, slots: draft.slots };
  }
}

/** Why C1 can't continue yet: no meal, or a meal with no calories set ("Dessert has no calories set"). */
export function amountProblems(draft: PrepDraft, settings: UserSettings | null): { reasons: string[]; missing: MealSlot[] } {
  if (draft.preset === null) return { reasons: ["Pick how much you're prepping"], missing: [] };
  const { slots } = amountOf(draft, settings);
  if (slots.length === 0) return { reasons: ["Pick at least one meal"], missing: [] };
  if (!settings) return { reasons: [], missing: [] };
  const planned = new Set(settings.slot_allocations.map((a) => a.slot));
  const missing = slots.filter((s) => !planned.has(s));
  return { reasons: missing.map((s) => `${MEAL_NAMES[s] ?? s} has no calories set`), missing };
}

export const MEAL_NAMES: Partial<Record<MealSlot, string>> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  snack: "Snack",
  protein_dessert: "Dessert",
  drink: "Drink",
};

/** A day choice as a date ("today" → today's date). */
export function dayOf(choice: DayChoice, today: Date): string {
  if (choice === "today") return toIso(today);
  if (choice === "tomorrow") return toIso(addDays(today, 1));
  return choice;
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  next.setDate(next.getDate() + days);
  return next;
}

/** The plan's days, as dates, from its start (the cook-day chips of C1b). */
export function planDays(draft: PrepDraft, settings: UserSettings | null, today: Date): string[] {
  const first = parseDay(dayOf(draft.start, today));
  const count = Math.min(amountOf(draft, settings).dayCount, MAX_PREP_DAYS);
  return Array.from({ length: count }, (_, i) => toIso(addDays(first, i)));
}

const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;

/** Your cook-day setting for a date's weekday. */
export function cookDayOf(settings: UserSettings | null, iso: string): CookDay | null {
  const key = WEEKDAY_KEYS[parseDay(iso).getDay()];
  return settings?.cook_schedule.find((d) => d.weekday === key) ?? null;
}

/** One big cook day's minutes before you change them: that day's own, or your longest cook day's (as the
 * server does, app/cook/prep.py). */
export function usualMinutes(settings: UserSettings | null, iso: string): number {
  const day = cookDayOf(settings, iso);
  if (day?.is_cook_day) return day.cook_minutes;
  const minutes = (settings?.cook_schedule ?? []).filter((d) => d.is_cook_day).map((d) => d.cook_minutes);
  return minutes.length ? Math.max(...minutes) : 90;
}

/** A few sessions, pre-filled: the plan's days that are cook days in your settings, with their minutes. */
export function defaultSessions(days: readonly string[], settings: UserSettings | null): { day: string; minutes: number }[] {
  return days.flatMap((day) => {
    const setting = cookDayOf(settings, day);
    return setting?.is_cook_day ? [{ day, minutes: setting.cook_minutes }] : [];
  });
}

/** "Today", "Tomorrow", "Wed 14". */
export function dayChipLabel(iso: string, today: Date): string {
  if (iso === toIso(today)) return "Today";
  if (iso === toIso(addDays(today, 1))) return "Tomorrow";
  const date = parseDay(iso);
  return `${["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][date.getDay()]} ${date.getDate()}`;
}

/** The choice to send for a date: "today" and "tomorrow" stay words, so Same as last time moves with you. */
export function choiceFor(iso: string, today: Date): DayChoice {
  if (iso === toIso(today)) return "today";
  if (iso === toIso(addDays(today, 1))) return "tomorrow";
  return iso;
}

/** Why C1b can't continue yet. */
export function styleProblems(draft: PrepDraft): string[] {
  if (draft.style === null) return ["Pick how you want to cook"];
  if (draft.style === "sessions" && !draft.sessions.some((s) => s.minutes > 0)) return ["Pick at least one cook day"];
  if ((draft.style === "big_day" || draft.style === "same_dish") && draft.cookMinutes === 0) return ["Give your cook day some time"];
  return [];
}

/** CookAnswers for POST /cook/meal-prep. Items added "have it" with Save to pantry were already added to your
 * pantry by the add flow, so nothing here saves anything. Sessions outside the plan's days (you shortened the
 * plan after picking them) are left out. */
export function buildPrepAnswers(draft: PrepDraft, settings: UserSettings | null, today: Date = new Date()): CookAnswers {
  const amount = amountOf(draft, settings);
  const quick = draft.goals.includes("quick");
  const style = draft.style ?? "mix";
  const days = new Set(planDays(draft, settings, today));
  return {
    schema_version: 1,
    mode: "prep",
    people: draft.people,
    goals: draft.goals.map((g) => GOAL_TILES[g]),
    mood: draft.mood,
    time_limit_minutes: quick ? (draft.quickMinutes ?? QUICK_DEFAULT_MINUTES) : null,
    pantry: draft.off.map((id) => ({ ingredient_id: id, include: false })),
    extras: draft.extras.map((e) => ({
      ingredient_id: e.ingredient_id,
      status: e.status,
      quantity: e.status === "have" && e.quantity ? e.quantity : null,
      unit: e.status === "have" && e.quantity ? (e.unit ?? null) : null,
      save_to_pantry: false,
    })),
    prep: {
      shape: amount.shape,
      slot: amount.shape === "portions" ? amount.slot : null,
      portions: amount.shape === "portions" ? amount.portions : null,
      day_count: amount.shape === "days" ? amount.dayCount : null,
      slots: amount.shape === "days" ? amount.slots : [],
      start: draft.start,
      extra_to_freeze: draft.extraToFreeze,
      cook_style: style,
      cook_day: style === "big_day" || style === "same_dish" ? (draft.cookDay ?? draft.start) : "today",
      cook_minutes: style === "big_day" || style === "same_dish" ? draft.cookMinutes : null,
      sessions: style === "sessions" ? draft.sessions.filter((s) => s.minutes > 0 && days.has(s.day)) : [],
    },
    shopping: draft.shopping ?? "make_a_list",
    budget_cents: draft.budgetCents,
    allow_llm: true,
  };
}

/** A new meal prep starting from your last answers. Extras are never carried over (C3: they come back as
 * chips); a start or cook day in the past becomes today. */
export function prepDraftFromAnswers(answers: Partial<CookAnswers> | null | undefined, today: Date = new Date()): PrepDraft {
  const draft = emptyPrepDraft();
  if (!answers || !answers.prep) return draft;
  const prep = answers.prep;
  const notPast = (choice: string | null | undefined): DayChoice => {
    if (!choice || choice === "today" || choice === "tomorrow") return (choice as DayChoice) ?? "today";
    return choice < toIso(today) ? "today" : choice;
  };
  const keys = Object.entries(GOAL_TILES);
  const shape = prep.shape === "days" ? "days" : "portions";
  const slots = (prep.slots ?? []) as MealSlot[];
  let preset: AmountPreset = "custom";
  if (shape === "portions" && prep.slot === "lunch" && prep.portions === 5) preset = "five_lunches";
  if (shape === "days" && prep.day_count === 5 && slots.length === 2 && slots.includes("lunch") && slots.includes("dinner")) preset = "lunch_dinner_5";
  const sessions = (prep.sessions ?? []).filter((s) => s.day >= toIso(today));
  return {
    ...draft,
    preset,
    shape,
    slot: (prep.slot as MealSlot | null) ?? null,
    portions: prep.portions ?? 5,
    dayCount: prep.day_count ?? 5,
    slots,
    start: notPast(prep.start as string),
    extraToFreeze: prep.extra_to_freeze ?? 0,
    style: (prep.cook_style as CookStyle | undefined) ?? "mix",
    cookDay: prep.cook_style === "big_day" || prep.cook_style === "same_dish" ? notPast(prep.cook_day as string) : null,
    cookMinutes: prep.cook_minutes ?? null,
    sessions,
    people: answers.people ?? null,
    goals: (answers.goals ?? []).flatMap((g) => keys.filter(([, tile]) => tile === g).map(([key]) => key as GoalKey)),
    quickMinutes: answers.time_limit_minutes ?? null,
    mood: answers.mood ?? null,
    off: (answers.pantry ?? []).filter((t) => !t.include).map((t) => t.ingredient_id),
    extras: [],
    shopping: answers.shopping ?? "make_a_list",
    budgetCents: answers.budget_cents ?? null,
  };
}

// ---------------- "No plan fits": each fix is the same answers with one change (M17, P4) ----------------
export function withTopUp(answers: CookAnswers, cents: number): CookAnswers {
  return { ...answers, shopping: "use_what_i_have", budget_cents: cents };
}

export function withShopping(answers: CookAnswers): CookAnswers {
  return { ...answers, shopping: "make_a_list", budget_cents: null };
}

export function withBudget(answers: CookAnswers, cents: number): CookAnswers {
  return { ...answers, shopping: "make_a_list", budget_cents: cents };
}

export function withMood(answers: CookAnswers, mood: RecipeMood): CookAnswers {
  return { ...answers, mood };
}

/** "Allow 65 min on Monday": that cook day gets the minutes. Mix it up becomes a few sessions on your cook days
 * (the same days and minutes), so one day can change; Quick is raised to match when it would cap the day. With
 * no day (no recipe fits any cook day), every cook day gets at least the minutes. */
export function withMinutes(answers: CookAnswers, day: string | null, minutes: number, settings: UserSettings | null, today: Date = new Date()): CookAnswers {
  const prep = answers.prep;
  if (!prep) return answers;
  const quick = (answers.goals ?? []).includes("quick") && (answers.time_limit_minutes ?? QUICK_DEFAULT_MINUTES) < minutes ? { time_limit_minutes: minutes } : {};
  const style = prep.cook_style ?? "mix";
  if (style === "big_day" || style === "same_dish") {
    return { ...answers, ...quick, prep: { ...prep, cook_minutes: Math.max(minutes, prep.cook_minutes ?? 0) } };
  }
  const draft = prepDraftFromAnswers(answers, today);
  const sessions = style === "sessions" ? (prep.sessions ?? []) : defaultSessions(planDays({ ...draft, preset: "custom" }, settings, today), settings);
  const raised = sessions.map((s) => (day === null || s.day === day ? { ...s, minutes: Math.max(s.minutes, minutes) } : s));
  if (day !== null && !raised.some((s) => s.day === day)) raised.push({ day, minutes });
  raised.sort((a, b) => (a.day < b.day ? -1 : 1));
  return { ...answers, ...quick, prep: { ...prep, cook_style: "sessions", sessions: raised } };
}

/** The "no plan fits" buttons (components/plan/NoPlanFits), each sending the answers again with its change. */
export function prepFixes(answers: CookAnswers, settings: UserSettings | null, rerun: (answers: CookAnswers) => void) {
  return {
    onTopUp: (cents: number) => rerun(withTopUp(answers, cents)),
    onShop: () => rerun(withShopping(answers)),
    onBudget: (cents: number) => rerun(withBudget(answers, cents)),
    onMinutes: (day: string | null, minutes: number) => rerun(withMinutes(answers, day, minutes, settings)),
    onMood: (_day: string | null, mood: string) => rerun(withMood(answers, mood as RecipeMood)),
    onRetry: () => rerun(answers),
  };
}

// ---------------- the draft on this device ----------------
function safeSession(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function loadPrepDraft(storage: Pick<Storage, "getItem"> | null = safeSession()): PrepDraft | null {
  try {
    const raw = storage?.getItem(PREP_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PrepDraft> | null;
    return parsed && typeof parsed === "object" ? { ...emptyPrepDraft(), ...parsed } : null;
  } catch {
    return null;
  }
}

export function savePrepDraft(draft: PrepDraft, storage: Pick<Storage, "setItem"> | null = safeSession()): void {
  try {
    storage?.setItem(PREP_DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // storage blocked: the draft lasts while this page is open
  }
}

export function clearPrepDraft(storage: Pick<Storage, "removeItem"> | null = safeSession()): void {
  try {
    storage?.removeItem(PREP_DRAFT_KEY);
  } catch {
    // nothing kept
  }
}
