// POST /api/v1/cook/meal-now answers with NDJSON (FLOW_SPEC §13.1 E2): started, progress, results (the full
// ranked list, replacing the last one), heartbeats, then one result. Step 2b.3b: with fewer than 6 good
// matches the server writes new ideas after the saved cards: `progress` "generating" (the "Writing new ideas…"
// strip), "waiting" with `wait_s` (the friendly countdown), then a second `results` with `new_version_ids`.
// This keeps the screen's state from the lines as they arrive. Display only: every card line comes from the
// server.
import { problemFrom, redirectToLogin } from "@/lib/api/client";
import { readNdjson } from "@/lib/api/ndjson";
import type { CookAnswers, CookStreamEvent, Problem, Suggestion } from "@/lib/api/types";

export type StageKey = "constraints" | "candidates";
export const STAGES: { key: StageKey; label: string }[] = [
  { key: "constraints", label: "Checking your pantry" },
  { key: "candidates", label: "Finding recipes" },
];

/** A rate-limit wait the server reported: the countdown runs from `seconds` at `startedAt` (only a timer). */
export type Wait = { seconds: number; startedAt: number };

export type MealNowState = {
  searchId: number | null;
  runId: number | null;
  stage: StageKey | null;
  suggestions: Suggestion[] | null; // null until the first `results` line
  status: "running" | "succeeded" | "partial" | "failed" | "lost";
  cached: boolean;
  header: string | null;
  goodMatches: number | null;
  ideasNeeded: boolean | null;
  emptyReason: string | null;
  emptyFilter: string | null;
  problem: Problem | null;
  elapsedS: number;
  generating: boolean; // new ideas are being written (the strip)
  wait: Wait | null; // a rate-limit wait during that (the strip's countdown)
  newIds: number[]; // the ideas the last results line added (New badges come with the cards)
  notes: string[]; // the result's notes ("I couldn't write new ideas just now…")
  retryAfterS: number | null;
};

export function initialState(): MealNowState {
  return {
    searchId: null,
    runId: null,
    stage: null,
    suggestions: null,
    status: "running",
    cached: false,
    header: null,
    goodMatches: null,
    ideasNeeded: null,
    emptyReason: null,
    emptyFilter: null,
    problem: null,
    elapsedS: 0,
    generating: false,
    wait: null,
    newIds: [],
    notes: [],
    retryAfterS: null,
  };
}

/** One stream line → the next state. `results` replaces the whole list; `result` ends the search. `now` (ms)
 * starts a wait's countdown. */
export function reduce(state: MealNowState, event: CookStreamEvent, now: number = Date.now()): MealNowState {
  const next: MealNowState = { ...state, elapsedS: event.elapsed_s ?? state.elapsedS };
  switch (event.event) {
    case "started":
      return { ...next, searchId: event.search_id, runId: event.run_id };
    case "progress":
      if (event.stage === "generating") return { ...next, generating: true, wait: null };
      if (event.stage === "waiting") return { ...next, wait: { seconds: event.wait_s ?? 0, startedAt: now } };
      return { ...next, stage: event.stage === "candidates" || event.stage === "constraints" ? event.stage : state.stage };
    case "results":
      return { ...next, suggestions: event.suggestions ?? [], stage: "candidates", newIds: event.new_version_ids ?? [], wait: null, generating: (event.new_version_ids ?? []).length > 0 ? false : state.generating };
    case "result":
      return {
        ...next,
        searchId: event.search_id,
        runId: event.run_id,
        status: event.status ?? "failed",
        cached: event.cached ?? false,
        header: event.header ?? null,
        goodMatches: event.good_matches ?? null,
        ideasNeeded: event.ideas_needed ?? null,
        emptyReason: event.empty_reason ?? null,
        emptyFilter: event.empty_filter ?? null,
        problem: event.problem ?? null,
        generating: false,
        wait: null,
        notes: event.notes ?? [],
        retryAfterS: event.retry_after_s ?? null,
      };
    default:
      return next; // heartbeat (`prefetched` comes only from More ideas, lib/cook/more.ts)
  }
}

/** The stream ended without its result line (the connection dropped): keep what arrived. */
export function lost(state: MealNowState): MealNowState {
  return state.status === "running" ? { ...state, status: "lost", generating: false, wait: null } : state;
}

/** POST an NDJSON request and stream its lines. Throws ApiError when the request itself is refused (422, 401). */
export async function streamLines<T>(path: string, body: unknown, onEvent: (event: T) => void, signal?: AbortSignal): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    const error = await problemFrom(response);
    if (response.status === 401) redirectToLogin();
    throw error;
  }
  await readNdjson<T>(response.body, onEvent);
}

/** Start a search and stream its lines. Throws ApiError when the request itself is refused (422, 401). */
export function streamMealNow(answers: CookAnswers, onEvent: (event: CookStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  return streamLines<CookStreamEvent>("/api/v1/cook/meal-now", answers, onEvent, signal);
}
