import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { StepsStreamEvent } from "@/lib/api/types";
import { reduceSteps, resetSteps, startingSteps, type StepsState, writeSteps } from "@/lib/cook/steps";

import { RecipeActions } from "./RecipeActions";
import { DAILY_STEPS, StepsPending } from "./StepsPending";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const line = (event: Partial<StepsStreamEvent> & Pick<StepsStreamEvent, "event">): StepsStreamEvent =>
  ({ version_id: 7, run_id: 3, elapsed_s: 0, ...event }) as StepsStreamEvent;

function pending(state: StepsState | null, onRetry = vi.fn(), online = true) {
  render(<StepsPending method="Sear the chicken, simmer the rice, wilt the spinach" state={state} online={online} onRetry={onRetry} />);
  return onRetry;
}

describe("C8 steps for a new idea", () => {
  afterEach(() => {
    resetSteps();
    vi.useRealTimers();
  });

  it("writing: the method line and 'Writing the steps for this one…' with Pottle working", () => {
    pending(startingSteps(7));
    expect(screen.getByText("Sear the chicken, simmer the rice, wilt the spinach")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Writing the steps for this one…");
  });

  it("a rate-limit wait shows the countdown in the Steps section, never an error", () => {
    vi.useFakeTimers({ now: 50_000 });
    const state = reduceSteps(startingSteps(7), line({ event: "progress", stage: "waiting", wait_s: 23 }), 50_000);
    pending(state);
    expect(screen.getByRole("status")).toHaveTextContent("The recipe service needs a short breather. Back in 0:23");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("a wait too long for the request: 'Ready in 0:45', then one tap continues", async () => {
    vi.useFakeTimers({ now: 10_000 });
    const state = reduceSteps(startingSteps(7), line({ event: "result", status: "waiting", retry_after_s: 45 }), 10_000);
    const onRetry = pending(state);
    expect(screen.getByRole("button", { name: "Ready in 0:45" })).toBeDisabled();
    await act(async () => {
      vi.advanceTimersByTime(45_500);
    });
    const button = screen.getByRole("button", { name: "Write the steps" });
    expect(button).toBeEnabled();
    vi.useRealTimers();
    await userEvent.click(button);
    expect(onRetry).toHaveBeenCalled();
  });

  it("failed: the plain message and Try again; the daily guard has its own message", async () => {
    const failed = reduceSteps(startingSteps(7), line({ event: "result", status: "failed", problem: { type: "about:blank", title: "I couldn't write the steps just now", status: 502, detail: "bad output" } }));
    const onRetry = pending(failed);
    expect(screen.getByRole("alert")).toHaveTextContent("I couldn't write the steps just now.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
    const daily = reduceSteps(startingSteps(7), line({ event: "result", status: "failed", problem: { type: "about:blank", title: DAILY_STEPS, status: 429, detail: "", code: "llm_daily_budget" } }));
    expect(daily.status).toBe("daily");
  });

  it("offline: the steps need a connection", () => {
    pending(null, vi.fn(), false);
    expect(screen.getByText("The steps need a connection.")).toBeInTheDocument();
  });

  it("Cook this reads 'Writing steps…' and stays disabled until the steps land", () => {
    const recipe = { recipe_id: 1, title: "Garlic chicken rice", is_favorite: false, is_saved: false };
    const { rerender } = render(<RecipeActions recipe={recipe} cook={{ meal: { version_id: 7, search_id: 5 } }} online blocked="Writing steps…" />);
    expect(screen.getByRole("button", { name: "Writing steps…" })).toBeDisabled();
    rerender(<RecipeActions recipe={recipe} cook={{ meal: { version_id: 7, search_id: 5 } }} online blocked={null} />);
    expect(screen.getByRole("button", { name: "Cook this" })).toBeEnabled();
  });

  it("the steps are asked for once per recipe, and the page reloads when they land", async () => {
    const stream = vi.fn(async (_id: number, _query: string, onEvent: (e: StepsStreamEvent) => void) => {
      onEvent(line({ event: "progress", stage: "writing_steps" }));
      onEvent(line({ event: "result", status: "succeeded" }));
    });
    const onReady = vi.fn();
    writeSteps(7, "search=5", onReady, stream);
    writeSteps(7, "search=5", onReady, stream); // a remount while it runs
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledTimes(1));
    expect(stream).toHaveBeenCalledTimes(1);
    expect(stream.mock.calls[0]?.[1]).toBe("search=5");
  });
});
