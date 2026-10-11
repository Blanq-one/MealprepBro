import { afterEach, describe, expect, it, vi } from "vitest";

import type { CookStreamEvent } from "@/lib/api/types";
import { suggestion } from "@/test/fixtures";

import { DAILY_NOTE, initialMore, moreState, reduceMore, resetMore, tapAction, tapMore } from "./more";

const line = (event: Partial<CookStreamEvent> & Pick<CookStreamEvent, "event">): CookStreamEvent =>
  ({ search_id: 5, run_id: 9, elapsed_s: 0, new_version_ids: [], notes: [], ...event }) as CookStreamEvent;

const shown = [suggestion({ version_id: 1 }), suggestion({ version_id: 2, badges: ["new"] })];
const held = [...shown, suggestion({ version_id: 3, badges: ["new"] })];

/** A fake E18: plays these lines, then ends. */
function e18(lines: CookStreamEvent[][]) {
  let call = 0;
  const stream = vi.fn(async (_searchId: number, onEvent: (e: CookStreamEvent) => void) => {
    for (const event of lines[call] ?? []) onEvent(event);
    call += 1;
  });
  return stream;
}

describe("More ideas", () => {
  afterEach(() => resetMore());

  it("the first tap always calls E18 live and waits (the strip, a countdown during a wait)", () => {
    let state = initialMore(5);
    expect(tapAction(state)).toBe("call");
    state = reduceMore(state, line({ event: "progress", stage: "generating" }));
    expect(state.live).toBe(true);
    state = reduceMore(state, line({ event: "progress", stage: "waiting", wait_s: 41 }), 2000);
    expect(state.wait).toEqual({ seconds: 41, startedAt: 2000 });
    state = reduceMore(state, line({ event: "results", suggestions: shown, new_version_ids: [2] }));
    expect(state).toMatchObject({ live: false, wait: null, newIds: [2] });
    expect(state.shown?.map((s) => s.version_id)).toEqual([1, 2]);
  });

  it("a held prefetched list is never shown before the next tap, then shows at once", () => {
    let state = reduceMore(initialMore(5), line({ event: "results", suggestions: shown, new_version_ids: [2] }));
    state = reduceMore(state, line({ event: "progress", stage: "prefetching" }));
    expect(state.writing).toBe(true);
    state = reduceMore(state, line({ event: "prefetched", suggestions: held, new_version_ids: [3] }));
    expect(state.shown?.map((s) => s.version_id)).toEqual([1, 2]); // still the tap's list
    expect(state.held?.map((s) => s.version_id)).toEqual([1, 2, 3]);
    expect(tapAction(state)).toBe("show_held");
  });

  it("a later tap shows the held batch at once and still calls E18 (exposures, the next batch)", async () => {
    const stream = e18([
      [line({ event: "progress", stage: "generating" }), line({ event: "results", suggestions: shown, new_version_ids: [2] }), line({ event: "progress", stage: "prefetching" }), line({ event: "prefetched", suggestions: held, new_version_ids: [3] }), line({ event: "result", status: "succeeded" })],
      [line({ event: "results", suggestions: held, new_version_ids: [3] }), line({ event: "progress", stage: "prefetching" }), line({ event: "result", status: "succeeded" })],
    ]);
    expect(tapMore(5, stream)).toBe("call");
    await vi.waitFor(() => expect(moreState(5).held).not.toBeNull());
    expect(tapMore(5, stream)).toBe("show_held");
    expect(moreState(5).shown?.map((s) => s.version_id)).toEqual([1, 2, 3]); // at once, before E18 answers
    expect(moreState(5).newIds).toEqual([3]);
    expect(moreState(5).live).toBe(false); // no strip: the cards are already on screen
    await vi.waitFor(() => expect(stream).toHaveBeenCalledTimes(2));
  });

  it("tapped while the next batch is written: the button reads Writing… and the ideas show when they land", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const stream = vi.fn(async (_id: number, onEvent: (e: CookStreamEvent) => void) => {
      if (stream.mock.calls.length > 1) return; // the follow-up call after the batch landed
      onEvent(line({ event: "results", suggestions: shown, new_version_ids: [2] }));
      onEvent(line({ event: "progress", stage: "prefetching" }));
      await gate;
      onEvent(line({ event: "prefetched", suggestions: held, new_version_ids: [3] }));
      onEvent(line({ event: "result", status: "succeeded" }));
    });
    tapMore(5, stream);
    await vi.waitFor(() => expect(moreState(5).writing).toBe(true));
    expect(tapMore(5, stream)).toBe("wait_for_writing");
    expect(moreState(5).wantMore).toBe(true);
    expect(tapAction(moreState(5))).toBe("ignore"); // further taps are ignored
    release();
    await vi.waitFor(() => expect(moreState(5).shown?.map((s) => s.version_id)).toEqual([1, 2, 3]));
    await vi.waitFor(() => expect(stream).toHaveBeenCalledTimes(2)); // that tap's E18: no second ideas call before
  });

  it("a wait too long ends with retry_after_s: More ideas is back at zero (only a timer)", () => {
    const state = reduceMore(initialMore(5), line({ event: "result", status: "partial", retry_after_s: 45, notes: ["The recipe service needs a short breather."] }), 10_000);
    expect(state.retry).toEqual({ seconds: 45, startedAt: 10_000 });
    expect(tapAction(state, 10_000 + 44_000)).toBe("ignore");
    expect(tapAction(state, 10_000 + 45_000)).toBe("call");
  });

  it("the daily allowance turns More ideas off with its note", () => {
    const state = reduceMore(initialMore(5), line({ event: "result", status: "partial", notes: [DAILY_NOTE] }));
    expect(state.daily).toBe(true);
    expect(tapAction(state)).toBe("ignore");
  });
});
