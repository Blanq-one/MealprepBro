import { afterEach, describe, expect, it, vi } from "vitest";

import type { CookAnswers, CookStreamEvent } from "@/lib/api/types";
import { suggestion } from "@/test/fixtures";

import { liveRun, resetRun, startRun } from "./liveRun";

const answers = { schema_version: 1, mode: "now", allow_llm: true } as CookAnswers;
const line = (event: Partial<CookStreamEvent> & Pick<CookStreamEvent, "event">): CookStreamEvent =>
  ({ search_id: 5, run_id: 9, elapsed_s: 0, new_version_ids: [], notes: [], ...event }) as CookStreamEvent;

describe("the live meal-now run", () => {
  afterEach(() => resetRun());

  it("is sent once per run key, however often the screen mounts", async () => {
    const stream = vi.fn(async (_answers: CookAnswers, onEvent: (e: CookStreamEvent) => void) => {
      onEvent(line({ event: "started" }));
      onEvent(line({ event: "results", suggestions: [suggestion()] }));
      onEvent(line({ event: "result", status: "succeeded" }));
    });
    startRun("a", answers, stream);
    startRun("a", answers, stream); // Strict Mode mounts twice
    await vi.waitFor(() => expect(liveRun()?.state.status).toBe("succeeded"));
    expect(stream).toHaveBeenCalledTimes(1);
    expect(liveRun()?.state.suggestions).toHaveLength(1);
  });

  it("a refused request is an error; a stream cut after some lines is lost", async () => {
    startRun("b", answers, async () => Promise.reject(new Error("422")));
    await vi.waitFor(() => expect(liveRun()?.error).toBeInstanceOf(Error));
    startRun("c", answers, async (_a, onEvent) => {
      onEvent(line({ event: "started" }));
      onEvent(line({ event: "results", suggestions: [suggestion()] }));
      throw new TypeError("network");
    });
    await vi.waitFor(() => expect(liveRun()?.state.status).toBe("lost"));
    expect(liveRun()?.error).toBeNull();
    expect(liveRun()?.state.suggestions).toHaveLength(1);
  });
});
