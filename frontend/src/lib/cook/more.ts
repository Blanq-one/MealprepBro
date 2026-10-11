// More ideas (E18, FLOW_SPEC C5 and §14), kept outside React per search so Back, a recipe and a remount never
// lose a held batch or send a tap twice.
//
//   first tap            POST /cook/searches/{id}/more: one ideas call, waited for (the strip, or a countdown)
//   later tap, held      the held `prefetched` list shows at once, and the tap still calls E18 (it logs those
//                        exposures and writes the next batch)
//   later tap, writing   the button reads "Writing…": the tap is remembered and the ideas show when they land
//   later tap, none held like the first tap
// A held list is never shown before a tap. A wait too long for the request ends with `retry_after_s`: the button
// reads "Ready in 0:45" and turns back into a normal button at zero. Display only: every card comes from the
// server.
import { useSyncExternalStore } from "react";

import type { CookStreamEvent, Suggestion } from "@/lib/api/types";

import { streamLines, type Wait } from "./stream";

export const DAILY_NOTE = "That's today's new-idea allowance; back tomorrow.";

export type MoreState = {
  searchId: number;
  live: boolean; // a tap's own ideas call is running (the strip)
  wait: Wait | null; // its rate-limit wait (the strip's countdown)
  writing: boolean; // the background batch is being written after the cards landed
  wantMore: boolean; // tapped while writing: show the batch as soon as it lands
  shown: Suggestion[] | null; // the list after the last tap (replaces the search's list)
  newIds: number[];
  held: Suggestion[] | null; // `prefetched`: kept until the next tap, never shown before
  heldIds: number[];
  retry: Wait | null; // "Ready in 0:45" on the button
  notes: string[];
  daily: boolean; // the daily allowance is used up
  error: unknown;
};

export function initialMore(searchId: number): MoreState {
  return {
    searchId,
    live: false,
    wait: null,
    writing: false,
    wantMore: false,
    shown: null,
    newIds: [],
    held: null,
    heldIds: [],
    retry: null,
    notes: [],
    daily: false,
    error: null,
  };
}

/** What a tap does now: show the held list at once (and call E18), wait for the batch being written, or call
 * E18 live. */
export type TapAction = "show_held" | "wait_for_writing" | "call" | "ignore";

export function tapAction(state: MoreState, now: number = Date.now()): TapAction {
  if (state.daily || state.live || state.wantMore) return "ignore";
  if (state.retry && now < state.retry.startedAt + state.retry.seconds * 1000) return "ignore";
  if (state.held) return "show_held";
  if (state.writing) return "wait_for_writing";
  return "call";
}

/** The held list becomes the shown list (its ideas carry New badges). */
export function showHeld(state: MoreState): MoreState {
  if (!state.held) return state;
  return { ...state, shown: state.held, newIds: state.heldIds, held: null, heldIds: [], wantMore: false };
}

export function reduceMore(state: MoreState, event: CookStreamEvent, now: number = Date.now()): MoreState {
  switch (event.event) {
    case "progress":
      if (event.stage === "generating") return { ...state, live: true, wait: null, retry: null };
      if (event.stage === "waiting") return { ...state, wait: { seconds: event.wait_s ?? 0, startedAt: now } };
      if (event.stage === "prefetching") return { ...state, live: false, wait: null, writing: true };
      return state;
    case "results":
      return { ...state, live: false, wait: null, shown: event.suggestions ?? state.shown, newIds: event.new_version_ids ?? [] };
    case "prefetched": {
      const held = { ...state, writing: false, held: event.suggestions ?? null, heldIds: event.new_version_ids ?? [] };
      return state.wantMore ? showHeld(held) : held;
    }
    case "result": {
      const notes = event.notes ?? [];
      const retry = event.retry_after_s ? { seconds: event.retry_after_s, startedAt: now } : null;
      return { ...state, live: false, wait: null, writing: false, wantMore: false, retry, notes, daily: notes.includes(DAILY_NOTE) };
    }
    default:
      return state; // started, heartbeat
  }
}

export function streamMore(searchId: number, onEvent: (event: CookStreamEvent) => void, signal?: AbortSignal): Promise<void> {
  return streamLines<CookStreamEvent>(`/api/v1/cook/searches/${searchId}/more`, undefined, onEvent, signal);
}

// ---------------- the store ----------------
const states = new Map<number, MoreState>();
const listeners = new Set<() => void>();
let version = 0;

function set(next: MoreState): void {
  states.set(next.searchId, next);
  version += 1;
  for (const listener of listeners) listener();
}

export function moreState(searchId: number): MoreState {
  return states.get(searchId) ?? initialMore(searchId);
}

type Stream = typeof streamMore;

/** One E18 request. `live`: the tap waits for its own ideas call (the strip); false when the held list is
 * already on screen. */
function call(searchId: number, stream: Stream, live: boolean): void {
  const onEvent = (event: CookStreamEvent) => {
    const before = moreState(searchId);
    set(reduceMore(before, event));
    if (before.wantMore && event.event === "prefetched") call(searchId, stream, false); // tapped while writing
    if (before.wantMore && event.event === "result" && !before.held) call(searchId, stream, true); // none came
  };
  set({ ...moreState(searchId), live, error: null, notes: [] });
  stream(searchId, onEvent)
    .then(() => {
      const s = moreState(searchId);
      if (s.live || s.writing) set({ ...s, live: false, writing: false, wait: null });
    })
    .catch((error: unknown) => set({ ...moreState(searchId), live: false, writing: false, wait: null, error }));
}

/** A More ideas tap. */
export function tapMore(searchId: number, stream: Stream = streamMore): TapAction {
  const state = moreState(searchId);
  const action = tapAction(state);
  if (action === "show_held") {
    set(showHeld(state));
    call(searchId, stream, false);
  } else if (action === "wait_for_writing") {
    set({ ...state, wantMore: true });
  } else if (action === "call") {
    call(searchId, stream, true);
  }
  return action;
}

/** Forget every search's More ideas (tests). */
export function resetMore(): void {
  states.clear();
  version += 1;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** This search's More ideas, kept up to date as lines arrive. */
export function useMore(searchId: number | null): MoreState | null {
  useSyncExternalStore(
    subscribe,
    () => version,
    () => 0,
  );
  return searchId === null ? null : moreState(searchId);
}
