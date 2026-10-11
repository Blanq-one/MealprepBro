// Steps for a new idea, written the first time it is opened (E19, FLOW_SPEC C8): POST
// /recipe-versions/{id}/steps streams `writing_steps`, `waiting` (with `wait_s`, the countdown in the Steps
// section) and `checking`, then one result: succeeded, waiting (try again at `retry_after_s`; never an error)
// or failed. One request per recipe at a time, kept outside React so a remount never sends it twice.
import { useEffect, useSyncExternalStore } from "react";

import type { Problem, StepsStreamEvent } from "@/lib/api/types";

import { streamLines, type Wait } from "./stream";

export const DAILY_CODE = "llm_daily_budget";

export type StepsState = {
  versionId: number;
  status: "writing" | "waiting" | "failed" | "daily" | "ready";
  wait: Wait | null; // a rate-limit wait while writing (the countdown)
  retry: Wait | null; // status waiting: "Ready in 0:45", then one tap continues
  problem: Problem | null;
};

export function startingSteps(versionId: number): StepsState {
  return { versionId, status: "writing", wait: null, retry: null, problem: null };
}

export function reduceSteps(state: StepsState, event: StepsStreamEvent, now: number = Date.now()): StepsState {
  if (event.event === "progress") {
    if (event.stage === "waiting") return { ...state, wait: { seconds: event.wait_s ?? 0, startedAt: now } };
    return { ...state, wait: null };
  }
  if (event.event !== "result") return state;
  if (event.status === "succeeded") return { ...state, status: "ready", wait: null, retry: null, problem: null };
  if (event.status === "waiting") {
    return { ...state, status: "waiting", wait: null, retry: { seconds: event.retry_after_s ?? 60, startedAt: now }, problem: null };
  }
  const daily = event.problem?.code === DAILY_CODE;
  return { ...state, status: daily ? "daily" : "failed", wait: null, problem: event.problem ?? null };
}

export function streamSteps(versionId: number, query: string, onEvent: (event: StepsStreamEvent) => void): Promise<void> {
  const suffix = query ? `?${query}` : "";
  return streamLines<StepsStreamEvent>(`/api/v1/recipe-versions/${versionId}/steps${suffix}`, undefined, onEvent);
}

// ---------------- the store ----------------
const states = new Map<number, StepsState>();
const running = new Set<number>();
const listeners = new Set<() => void>();
let version = 0;

function set(next: StepsState): void {
  states.set(next.versionId, next);
  version += 1;
  for (const listener of listeners) listener();
}

type Stream = typeof streamSteps;

/** Write the steps (once at a time per recipe). `onReady` reloads the page, which then has its steps. */
export function writeSteps(versionId: number, query: string, onReady: () => void, stream: Stream = streamSteps): void {
  if (running.has(versionId)) return;
  running.add(versionId);
  set(startingSteps(versionId));
  stream(versionId, query, (event) => {
    const next = reduceSteps(states.get(versionId) ?? startingSteps(versionId), event);
    set(next);
    if (next.status === "ready") onReady();
  })
    .then(() => {
      const s = states.get(versionId);
      if (s && s.status === "writing") set({ ...s, status: "failed", wait: null });
    })
    .catch((error: unknown) => {
      const detail = error instanceof Error ? error.message : "The connection dropped.";
      set({ ...(states.get(versionId) ?? startingSteps(versionId)), status: "failed", wait: null, problem: { type: "about:blank", title: "I couldn't write the steps just now", status: 0, detail } });
    })
    .finally(() => running.delete(versionId));
}

/** Forget every recipe's steps state (tests). */
export function resetSteps(): void {
  states.clear();
  running.clear();
  version += 1;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** An idea's steps: starts writing them on first open when they aren't ready and you're online. Null when the
 * recipe already has its steps. */
export function useSteps(versionId: number | null, ready: boolean, query: string, online: boolean, onReady: () => void): StepsState | null {
  useSyncExternalStore(
    subscribe,
    () => version,
    () => 0,
  );
  const needed = versionId !== null && !ready;
  useEffect(() => {
    if (needed && online && versionId !== null && !states.has(versionId)) writeSteps(versionId, query, onReady);
  }, [needed, online, versionId, query, onReady]);
  if (!needed || versionId === null) return null;
  return states.get(versionId) ?? null;
}
