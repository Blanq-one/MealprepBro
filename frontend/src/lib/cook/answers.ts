// The meal-now answers (FLOW_SPEC §7 C2–C3): kept as a draft on this device while you answer, then sent as
// CookAnswers. Nothing here computes a number; the server resolves the meal, people, mood and goals.
import type { CookAnswers, ExtraItem, GoalTile, MealSlot, RecipeMood } from "@/lib/api/types";
import type { GoalKey } from "@/lib/format/icons";

/** The goal tiles' keys on screen → the API's goal names. */
export const GOAL_TILES: Record<GoalKey, GoalTile> = {
  protein: "high_protein",
  carb: "high_carb",
  iron: "iron_rich",
  low_calorie: "low_calorie",
  cheap: "cheap",
  quick: "quick",
};

/** An item you added on "What do you have?": its name for the chip, and what you said about it. */
export type DraftExtra = {
  ingredient_id: number;
  name: string;
  status: "have" | "could_buy";
  /** "Have it" with an amount: a package preset key, or a custom amount in a server unit. */
  preset?: string | null;
  presetLabel?: string | null;
  quantity?: string | null;
  unit?: string | null;
  saveToPantry?: boolean;
};

export type MealNowDraft = {
  slot: MealSlot | null; // you pick it every time (M9); null = not picked yet
  people: number | null; // null = your household size
  goals: GoalKey[]; // in tap order
  quickMinutes: number | null; // with Quick
  mood: RecipeMood | null; // null = today's mood in your schedule
  off: number[]; // pantry items turned off for this search (ingredient ids)
  extras: DraftExtra[];
};

export const DRAFT_KEY = "mealbro.cook.now";
export const QUICK_DEFAULT_MINUTES = 30;

export function emptyDraft(): MealNowDraft {
  return { slot: null, people: null, goals: [], quickMinutes: null, mood: null, off: [], extras: [] };
}

/** A new search starting from your last answers. The meal is never carried over (M9: you pick it each time;
 * Same as last time covers repeats), and neither are last time's extras. */
export function draftFromAnswers(answers: Partial<CookAnswers> | null | undefined): MealNowDraft {
  if (!answers) return emptyDraft();
  const keys = Object.entries(GOAL_TILES);
  return {
    slot: null,
    people: answers.people ?? null,
    goals: (answers.goals ?? []).flatMap((g) => keys.filter(([, tile]) => tile === g).map(([key]) => key as GoalKey)),
    quickMinutes: answers.time_limit_minutes ?? null,
    mood: answers.mood ?? null,
    off: (answers.pantry ?? []).filter((t) => !t.include).map((t) => t.ingredient_id),
    extras: [], // last time's extras come back as chips, never pre-selected (C3)
  };
}

/** CookAnswers for POST /cook/meal-now: only the pantry items you turned off are sent (C3). */
export function buildAnswers(draft: MealNowDraft): CookAnswers {
  const extras: ExtraItem[] = draft.extras.map((e) => ({
    ingredient_id: e.ingredient_id,
    status: e.status,
    quantity: e.status === "have" && e.quantity ? e.quantity : null,
    unit: e.status === "have" && e.quantity ? (e.unit ?? null) : null,
    save_to_pantry: false, // saved to Pantry with POST /inventory/bulk before the search, if you asked
  }));
  const quick = draft.goals.includes("quick");
  return {
    schema_version: 1,
    mode: "now",
    slot: draft.slot,
    people: draft.people,
    goals: draft.goals.map((g) => GOAL_TILES[g]),
    mood: draft.mood,
    time_limit_minutes: quick ? (draft.quickMinutes ?? QUICK_DEFAULT_MINUTES) : null,
    pantry: draft.off.map((id) => ({ ingredient_id: id, include: false })),
    extras,
    allow_llm: true,
  };
}

export function loadDraft(storage: Pick<Storage, "getItem"> | null = safeSession()): MealNowDraft | null {
  try {
    const raw = storage?.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<MealNowDraft> | null;
    if (!parsed || typeof parsed !== "object") return null;
    return { ...emptyDraft(), ...parsed };
  } catch {
    return null;
  }
}

export function saveDraft(draft: MealNowDraft, storage: Pick<Storage, "setItem"> | null = safeSession()): void {
  try {
    storage?.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // storage blocked: the draft lasts while this page is open
  }
}

export function clearDraft(storage: Pick<Storage, "removeItem"> | null = safeSession()): void {
  try {
    storage?.removeItem(DRAFT_KEY);
  } catch {
    // nothing kept
  }
}

/** The answers the results screen sends next (Find recipes, Same as last time, an empty state's fix), under a
 * one-off key in the URL (`/cook/results/?run=<key>`), so a reload never sends another run's answers. */
export const PENDING_KEY = "mealbro.cook.pending";

let fallbackPending: { run: string; answers: CookAnswers } | null = null; // when session storage is blocked

export function savePending(answers: CookAnswers, storage: Pick<Storage, "setItem"> | null = safeSession()): string {
  const run = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  fallbackPending = { run, answers };
  try {
    storage?.setItem(PENDING_KEY, JSON.stringify(fallbackPending));
  } catch {
    // kept in memory for this page
  }
  return run;
}

export function loadPending(run: string, storage: Pick<Storage, "getItem"> | null = safeSession()): CookAnswers | null {
  try {
    const raw = storage?.getItem(PENDING_KEY);
    const parsed = raw ? (JSON.parse(raw) as { run?: string; answers?: CookAnswers }) : fallbackPending;
    return parsed && parsed.run === run && parsed.answers ? parsed.answers : null;
  } catch {
    return fallbackPending && fallbackPending.run === run ? fallbackPending.answers : null;
  }
}

function safeSession(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

/** The quick limits you can step through, and the next one up (the empty state's "Allow 45 min"). */
export const QUICK_STEPS = [10, 15, 20, 30, 45, 60, 90, 120] as const;

export function nextQuick(minutes: number | null): number | null {
  const current = minutes ?? QUICK_DEFAULT_MINUTES;
  return QUICK_STEPS.find((m) => m > current) ?? null;
}

export const MOODS: readonly RecipeMood[] = ["simple", "medium", "fancy"];
