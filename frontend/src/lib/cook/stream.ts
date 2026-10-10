// POST /api/v1/cook/meal-now answers with NDJSON (FLOW_SPEC §13.1 E2): started, progress, results (the full
// ranked list, replacing the last one), heartbeats, then one result. This keeps the screen's state from the
// lines as they arrive. Display only: every card line comes from the server.
import { problemFrom, redirectToLogin } from "@/lib/api/client";
import { readNdjson } from "@/lib/api/ndjson";
import type { CookAnswers, CookStreamEvent, Problem, Suggestion } from "@/lib/api/types";

export type StageKey = "constraints" | "candidates";
export const STAGES: { key: StageKey; label: string }[] = [
  { key: "constraints", label: "Checking your pantry" },
  { key: "candidates", label: "Finding recipes" },
];

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
  };
}

/** One stream line → the next state. `results` replaces the whole list; `result` ends the search. */
export function reduce(state: MealNowState, event: CookStreamEvent): MealNowState {
  const next: MealNowState = { ...state, elapsedS: event.elapsed_s ?? state.elapsedS };
  switch (event.event) {
    case "started":
      return { ...next, searchId: event.search_id, runId: event.run_id };
    case "progress":
      return { ...next, stage: event.stage === "candidates" || event.stage === "constraints" ? event.stage : state.stage };
    case "results":
      return { ...next, suggestions: event.suggestions ?? [], stage: "candidates" };
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
      };
    default:
      return next; // heartbeat; `prefetched` arrives with More ideas (step 2b.3b)
  }
}

/** The stream ended without its result line (the connection dropped): keep what arrived. */
export function lost(state: MealNowState): MealNowState {
  return state.status === "running" ? { ...state, status: "lost" } : state;
}

/** Start a search and stream its lines. Throws ApiError when the request itself is refused (422, 401). */
export async function streamMealNow(
  answers: CookAnswers,
  onEvent: (event: CookStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/v1/cook/meal-now", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: JSON.stringify(answers),
    signal,
  });
  if (!response.ok || !response.body) {
    const error = await problemFrom(response);
    if (response.status === 401) redirectToLogin();
    throw error;
  }
  await readNdjson<CookStreamEvent>(response.body, onEvent);
}
