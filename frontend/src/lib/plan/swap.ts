// Swap one meal (step 2b.6, E5, AA4). The sheet's options come as NDJSON (POST …/swap-options): started,
// progress (finding, generating, waiting with `wait_s`, checking), heartbeats, one result with 3-5 options.
// One tap applies an option (POST …/swap): a new version of the plan, which Undo brings back (POST
// /plans/{id}/swap/undo). Display only: every number and line is the server's.
import { api, problemFrom, redirectToLogin } from "@/lib/api/client";
import { readNdjson } from "@/lib/api/ndjson";
import type { PlanSummary, Problem, SwapBody, SwapMeal, SwapOption, SwapOptionsBody, SwapResult, SwapStreamEvent } from "@/lib/api/types";
import type { Wait } from "@/lib/cook/stream";

export type SwapSheetState = {
  status: "finding" | "ready" | "none_fit" | "waiting" | "failed" | "lost";
  message: string | null; // the stage line ("Finding meals that fit")
  writing: boolean; // Write a new one is running (its ideas call)
  wait: Wait | null; // a rate-limit wait during that call: the countdown
  retry: Wait | null; // the call had to wait longer than the request could: try again after this
  current: SwapMeal | null;
  options: SwapOption[];
  noFit: string | null;
  afterShopping: boolean;
  canWriteNew: boolean;
  notes: string[];
  problem: Problem | null;
};

export function initialSwap(): SwapSheetState {
  return { status: "finding", message: null, writing: false, wait: null, retry: null, current: null, options: [], noFit: null, afterShopping: false, canWriteNew: true, notes: [], problem: null };
}

/** The sheet's state after one line of the options stream. `now` is the clock for the countdowns. */
export function reduceSwap(state: SwapSheetState, event: SwapStreamEvent, now: number = Date.now()): SwapSheetState {
  if (event.event === "progress") {
    if (event.stage === "waiting") return { ...state, message: event.message ?? null, wait: { seconds: event.wait_s ?? 1, startedAt: now } };
    return { ...state, message: event.message ?? null, writing: event.stage === "generating" ? true : state.writing, wait: event.stage === "generating" ? state.wait : null };
  }
  if (event.event !== "result") return state;
  const done = { ...state, writing: false, wait: null, current: event.current ?? state.current, notes: event.notes ?? [], canWriteNew: event.can_write_new ?? state.canWriteNew, afterShopping: event.after_shopping ?? false };
  if (event.status === "waiting") return { ...done, status: "waiting", retry: { seconds: event.retry_after_s ?? 30, startedAt: now } };
  if (event.status === "failed") return { ...done, status: "failed", problem: event.problem ?? null };
  if (event.status === "none_fit") return { ...done, status: "none_fit", options: [], noFit: event.no_fit ?? null, retry: null };
  return { ...done, status: "ready", options: event.options ?? [], noFit: null, retry: null };
}

/** Stream the options for one meal. Throws ApiError when the request itself is refused. */
export async function streamSwapOptions(planId: number, mealId: number, body: SwapOptionsBody, onEvent: (event: SwapStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`/api/v1/plans/${planId}/meals/${mealId}/swap-options`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    const error = await problemFrom(response);
    if (response.status === 401) redirectToLogin();
    throw error;
  }
  await readNdjson<SwapStreamEvent>(response.body, onEvent);
}

export function applySwap(planId: number, mealId: number, body: SwapBody): Promise<SwapResult> {
  return api<SwapResult>(`/api/v1/plans/${planId}/meals/${mealId}/swap`, { method: "POST", json: body });
}

export function undoSwap(planId: number): Promise<PlanSummary> {
  return api<PlanSummary>(`/api/v1/plans/${planId}/swap/undo`, { method: "POST" });
}

/** The recipes already swapped away for one meal (by day and slot), so the next swap skips them (AC 2). */
export type SwappedAway = Record<string, number[]>;

export function mealKey(eatOn: string, slot: string): string {
  return `${eatOn}/${slot}`;
}

export function withSwappedAway(away: SwappedAway, key: string, versionId: number): SwappedAway {
  const list = away[key] ?? [];
  return list.includes(versionId) ? away : { ...away, [key]: [...list, versionId] };
}
