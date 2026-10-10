// One meal-now search in flight, kept outside React so a remount (Strict Mode, Back, the URL moving to
// `?search=<id>`) never sends it twice and never loses the lines that already arrived.
import { useSyncExternalStore } from "react";

import type { CookAnswers, CookStreamEvent } from "@/lib/api/types";

import { initialState, lost, type MealNowState, reduce, streamMealNow } from "./stream";

export type LiveRun = { run: string; state: MealNowState; error: unknown };

type Stream = typeof streamMealNow;

let current: LiveRun | null = null;
const listeners = new Set<() => void>();

function set(next: LiveRun): void {
  current = next;
  for (const listener of listeners) listener();
}

/** Start the search for `run` once; later calls with the same key return the run already going. */
export function startRun(run: string, answers: CookAnswers, stream: Stream = streamMealNow): LiveRun {
  if (current && current.run === run) return current;
  set({ run, state: initialState(), error: null });
  const onEvent = (event: CookStreamEvent) => {
    if (current?.run !== run) return;
    set({ ...current, state: reduce(current.state, event) });
  };
  stream(answers, onEvent)
    .then(() => {
      if (current?.run === run) set({ ...current, state: lost(current.state) });
    })
    .catch((error: unknown) => {
      if (current?.run !== run) return;
      // refused before any line (422, offline): an error; after some lines, the connection was lost
      const started = current.state.searchId !== null;
      set({ ...current, error: started ? null : error, state: started ? lost(current.state) : { ...current.state, status: "failed" } });
    });
  return current as LiveRun;
}

export function liveRun(): LiveRun | null {
  return current;
}

/** Forget the run (tests, or Try again). */
export function resetRun(): void {
  current = null;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The run for `run`, kept up to date as lines arrive (null when it isn't the one in flight). */
export function useLiveRun(run: string | null): LiveRun | null {
  const snapshot = useSyncExternalStore(
    subscribe,
    () => current,
    () => null,
  );
  return snapshot && run !== null && snapshot.run === run ? snapshot : null;
}
