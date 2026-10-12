// One meal-prep plan in flight (POST /api/v1/cook/meal-prep, NDJSON), kept outside React like the meal-now
// search (liveRun.ts): a remount (Strict Mode, Back) never sends it twice and never loses the lines that arrived.
// Display only: the stages, the countdown and the result are the server's.
import { useSyncExternalStore } from "react";

import type { CookAnswers, PlanStreamEvent, Problem } from "@/lib/api/types";

import { streamLines } from "./stream";

/** The building steps (FLOW_SPEC §5.4, §13.6): the server's stages under these names, in this order. */
export const PREP_STAGES = [
  { key: "pantry", label: "Checking your pantry", stages: ["queued", "constraints"] },
  { key: "recipes", label: "Finding recipes", stages: ["candidates", "generating", "waiting"] },
  { key: "calories", label: "Balancing calories across the days", stages: ["solving", "re-solving"] },
  { key: "groceries", label: "Pricing your groceries", stages: ["pricing"] },
  { key: "checking", label: "Double-checking every number", stages: ["validating"] },
] as const;

export type PrepRunState = {
  runId: number | null;
  stage: string | null; // the server's last stage
  message: string | null; // its words ("Finding recipes: writing new ones for lunch")
  wait: { seconds: number; startedAt: number } | null; // a rate-limit wait: the countdown
  elapsedS: number;
  status: "running" | "succeeded" | "infeasible" | "failed" | "lost";
  planId: number | null;
  problem: Problem | null;
  notes: string[];
  retryAfterS: number | null;
  rounding: boolean; // a re-solve after rounding ("Adjusting after rounding")
};

export function initialPrepState(): PrepRunState {
  return { runId: null, stage: null, message: null, wait: null, elapsedS: 0, status: "running", planId: null, problem: null, notes: [], retryAfterS: null, rounding: false };
}

/** One stream line → the next state. `now` (ms) starts a wait's countdown. */
export function reducePrep(state: PrepRunState, event: PlanStreamEvent, now: number = Date.now()): PrepRunState {
  const next: PrepRunState = { ...state, runId: event.run_id ?? state.runId, elapsedS: event.elapsed_s ?? state.elapsedS };
  if (event.event === "progress") {
    const stage = event.stage ?? state.stage;
    return {
      ...next,
      stage,
      message: event.message ?? state.message,
      wait: stage === "waiting" ? { seconds: event.wait_s ?? 0, startedAt: now } : null,
      rounding: stage === "re-solving" || (state.rounding && stage !== "solving"),
    };
  }
  if (event.event === "result") {
    return {
      ...next,
      status: event.status ?? "failed",
      planId: event.plan_id ?? null,
      problem: event.problem ?? null,
      notes: event.notes ?? [],
      retryAfterS: event.retry_after_s ?? null,
      wait: null,
    };
  }
  return next; // started, heartbeat
}

/** The steps' marks: everything before the current one is done. */
export function prepStages(state: PrepRunState): { key: string; label: string; state: "done" | "current" | "pending"; note?: string | null }[] {
  const at = Math.max(
    0,
    PREP_STAGES.findIndex((s) => (s.stages as readonly string[]).includes(state.stage ?? "")),
  );
  return PREP_STAGES.map((s, i) => ({
    key: s.key,
    label: s.label,
    state: state.status === "succeeded" || i < at ? "done" : i === at ? "current" : "pending",
    note: i === at && s.key === "recipes" && state.stage === "generating" ? state.message : i === at && s.key === "calories" && state.rounding ? "Adjusting after rounding" : null,
  }));
}

export type PrepRun = { run: string; state: PrepRunState; error: unknown };
type Stream = (answers: CookAnswers, onEvent: (event: PlanStreamEvent) => void) => Promise<void>;

export function streamMealPrep(answers: CookAnswers, onEvent: (event: PlanStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  return streamLines<PlanStreamEvent>("/api/v1/cook/meal-prep", answers, onEvent, signal);
}

let current: PrepRun | null = null;
const listeners = new Set<() => void>();

function set(next: PrepRun | null): void {
  current = next;
  for (const listener of listeners) listener();
}

/** Start the plan for `run` once; later calls with the same key return the run already going. */
export function startPrepRun(run: string, answers: CookAnswers, stream: Stream = streamMealPrep): PrepRun {
  if (current && current.run === run) return current;
  set({ run, state: initialPrepState(), error: null });
  stream(answers, (event) => {
    if (current?.run === run) set({ ...current, state: reducePrep(current.state, event) });
  })
    .then(() => {
      if (current?.run === run && current.state.status === "running") set({ ...current, state: { ...current.state, status: "lost", wait: null } });
    })
    .catch((error: unknown) => {
      if (current?.run !== run) return;
      // refused before any line (422: answers that can't make a plan, offline): an error; after some, lost
      const started = current.state.runId !== null;
      set({ ...current, error: started ? null : error, state: { ...current.state, status: started ? "lost" : "failed", wait: null } });
    });
  return current as unknown as PrepRun;
}

export function prepRun(): PrepRun | null {
  return current;
}

export function resetPrepRun(): void {
  set(null);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The run for `run`, kept up to date as lines arrive (null when it isn't the one in flight). */
export function usePrepRun(run: string | null): PrepRun | null {
  const snapshot = useSyncExternalStore(
    subscribe,
    () => current,
    () => null,
  );
  return snapshot && run !== null && snapshot.run === run ? snapshot : null;
}
