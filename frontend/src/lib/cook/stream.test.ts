import { describe, expect, it } from "vitest";

import type { CookStreamEvent } from "@/lib/api/types";
import { suggestion } from "@/test/fixtures";

import { initialState, lost, reduce } from "./stream";

const line = (event: Partial<CookStreamEvent> & Pick<CookStreamEvent, "event">): CookStreamEvent =>
  ({ search_id: 5, run_id: 9, elapsed_s: 0.2, new_version_ids: [], notes: [], ...event }) as CookStreamEvent;

describe("the meal-now stream reducer", () => {
  it("each results line replaces the whole list, in the server's order", () => {
    let state = reduce(initialState(), line({ event: "started" }));
    expect(state).toMatchObject({ searchId: 5, runId: 9, suggestions: null, status: "running" });
    state = reduce(state, line({ event: "progress", stage: "constraints" }));
    expect(state.stage).toBe("constraints");
    state = reduce(state, line({ event: "results", suggestions: [suggestion({ version_id: 1 }), suggestion({ version_id: 2 })] }));
    expect(state.suggestions?.map((s) => s.version_id)).toEqual([1, 2]);
    state = reduce(state, line({ event: "results", suggestions: [suggestion({ version_id: 3 })] }));
    expect(state.suggestions?.map((s) => s.version_id)).toEqual([3]); // replaced, never merged on the phone
    expect(state.stage).toBe("candidates");
    state = reduce(state, line({ event: "heartbeat", elapsed_s: 5.1 }));
    expect(state.elapsedS).toBe(5.1);
  });

  it("the result line ends the search: succeeded, partial or failed, with the empty state's reason", () => {
    const running = reduce(initialState(), line({ event: "results", suggestions: [] }));
    const partial = reduce(running, line({ event: "result", status: "partial", header: "Dinner for 1 · Quick", empty_reason: "Nothing fits 20 minutes.", empty_filter: "time" }));
    expect(partial).toMatchObject({ status: "partial", header: "Dinner for 1 · Quick", emptyReason: "Nothing fits 20 minutes.", emptyFilter: "time", suggestions: [] });
    const failed = reduce(initialState(), line({ event: "result", status: "failed", problem: { status: 502, title: "That didn't work", detail: "bad output", type: "about:blank" } }));
    expect(failed.status).toBe("failed");
    expect(failed.problem?.title).toBe("That didn't work");
  });

  it("a stream that ends without its result line is lost, keeping what arrived", () => {
    const some = reduce(initialState(), line({ event: "results", suggestions: [suggestion()] }));
    const gone = lost(some);
    expect(gone.status).toBe("lost");
    expect(gone.suggestions).toHaveLength(1);
    const done = reduce(some, line({ event: "result", status: "succeeded" }));
    expect(lost(done).status).toBe("succeeded"); // a finished search stays finished
  });
});
