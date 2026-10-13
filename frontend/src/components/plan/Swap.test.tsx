import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SwapOption, SwapResult, SwapStreamEvent } from "@/lib/api/types";
import { initialSwap, reduceSwap, withSwappedAway } from "@/lib/plan/swap";
import { batch, day, meal, plan } from "@/test/fixtures";

import { PlanView, type SwapProps } from "./PlanView";
import { SwapSheet, SwapToast } from "./Swap";

type Call = { method: string; path: string; body: unknown };

function option(overrides: Partial<SwapOption> = {}): SwapOption {
  return {
    version_id: 7,
    recipe_id: 7,
    title: "Lentil stew",
    dish_category: "soup",
    kcal: 540,
    protein_g: "31.0",
    numbers: ["540 kcal", "31.0 g protein", "about $1.40 a portion"],
    cost_delta_cents: 0,
    cost_delta_display: "No extra groceries",
    source_display: "Cook it Wed 14",
    also_changed: ["Mon 12's Chicken over rice: 4 → 3 portions"],
    buys: [],
    is_new: false,
    steps_ready: true,
    is_draft: false,
    ...overrides,
  };
}

const CURRENT = { plan_meal_id: 101, eat_on: "2026-10-14", slot: "dinner" as const, version_id: 3, title: "Chicken over rice", kcal: 560, protein_g: "42.0", label: "Wed 14 dinner" };

function result(overrides: Partial<SwapStreamEvent> = {}): SwapStreamEvent {
  return { event: "result", plan_id: 5, meal_id: 101, elapsed_s: 1, status: "succeeded", current: CURRENT, options: [option(), option({ version_id: 8, title: "Bean bowl", cost_delta_cents: 120, cost_delta_display: "+$1.20 groceries" })], can_write_new: true, after_shopping: false, notes: [], new_version_ids: [], ...overrides } as SwapStreamEvent;
}

/** fetch for the sheet: the options stream answers with these NDJSON lines (one list per request, in turn), the
 * swap with `swapped`. */
function stubFetch(streams: SwapStreamEvent[][], swapped?: SwapResult): Call[] {
  const calls: Call[] = [];
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ method: (init.method ?? "GET").toUpperCase(), path: url, body: typeof init.body === "string" ? JSON.parse(init.body) : undefined });
      if (url.endsWith("/swap-options")) {
        const lines = streams[Math.min(n, streams.length - 1)] ?? [];
        n += 1;
        const text = [{ event: "started", plan_id: 5, meal_id: 101, elapsed_s: 0 }, ...lines].map((l) => JSON.stringify(l)).join("\n");
        return new Response(text, { status: 200, headers: { "content-type": "application/x-ndjson" } });
      }
      if (url.endsWith("/swap") && swapped) return new Response(JSON.stringify(swapped), { status: 200, headers: { "content-type": "application/json" } });
      return new Response(JSON.stringify({ title: "Not found", detail: url }), { status: 404, headers: { "content-type": "application/problem+json" } });
    }),
  );
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("the options stream, as the sheet sees it", () => {
  it("finding, a rate-limit countdown while writing a new one, then the options", () => {
    let s = initialSwap();
    const line = (fields: Partial<SwapStreamEvent>) => ({ event: "progress", plan_id: 5, meal_id: 101, elapsed_s: 0, ...fields }) as SwapStreamEvent;
    s = reduceSwap(s, line({ stage: "generating", message: "Writing a new one" }));
    expect(s).toMatchObject({ status: "finding", writing: true });
    s = reduceSwap(s, line({ stage: "waiting", message: "The recipe service needs a short breather", wait_s: 23 }), 1000);
    expect(s.wait).toEqual({ seconds: 23, startedAt: 1000 });
    s = reduceSwap(s, result());
    expect(s).toMatchObject({ status: "ready", writing: false, wait: null });
    expect(s.options.map((o) => o.title)).toEqual(["Lentil stew", "Bean bowl"]);
  });

  it("none fits, a wait too long (try again later), and a failure", () => {
    expect(reduceSwap(initialSwap(), result({ status: "none_fit", options: [], no_fit: "No other dinner fits Wednesday's calories and cook time." }))).toMatchObject({ status: "none_fit", noFit: "No other dinner fits Wednesday's calories and cook time." });
    expect(reduceSwap(initialSwap(), result({ status: "waiting", options: [], retry_after_s: 45 }), 5).retry).toEqual({ seconds: 45, startedAt: 5 });
    const failed = reduceSwap(initialSwap(), result({ status: "failed", options: [], problem: { type: "about:blank", title: "Can't swap this meal", status: 409, detail: "This meal's day has passed.", diagnostics: [] } }));
    expect(failed).toMatchObject({ status: "failed" });
    expect(failed.problem?.detail).toBe("This meal's day has passed.");
  });

  it("remembers what you swapped away, per meal", () => {
    const away = withSwappedAway(withSwappedAway({}, "2026-10-14/dinner", 3), "2026-10-14/dinner", 7);
    expect(away).toEqual({ "2026-10-14/dinner": [3, 7] });
    expect(withSwappedAway(away, "2026-10-14/dinner", 3)).toBe(away);
  });
});

describe("the Swap sheet", () => {
  const dinner = meal({ eat_on: "2026-10-14", slot: "dinner", plan_meal_id: 101 });

  it("shows the meal now and its options; one tap swaps it, sending what was offered and swapped away", async () => {
    const swapped = { plan_id: 6, undo_plan_id: 5, plan_meal_id: 202, message: "Swapped. Also changed: Mon 12's Chicken over rice: 4 → 3 portions.", also_changed: [], plan: plan({ id: 6 }) } as SwapResult;
    const calls = stubFetch([[result()]], swapped);
    const onSwapped = vi.fn();
    render(<SwapSheet planId={5} meal={dinner} away={[2]} online onClose={() => undefined} onSwapped={onSwapped} />);
    expect(await screen.findByText("Lentil stew")).toBeInTheDocument();
    expect(screen.getByText(/Now:/)).toHaveTextContent("Now: Chicken over rice · 560 kcal · 42.0 g protein");
    expect(screen.getByRole("dialog", { name: "Swap Wed 14 dinner" })).toBeInTheDocument();
    expect(calls[0]?.body).toEqual({ exclude_version_ids: [2], allow_llm: false, allow_buying: false });
    const lentils = screen.getByRole("button", { name: "Swap to Lentil stew" });
    expect(lentils).toHaveTextContent("540 kcal · 31.0 g protein · about $1.40 a portion");
    expect(lentils).toHaveTextContent("No extra groceries");
    expect(lentils).toHaveTextContent("Also changes: Mon 12's Chicken over rice: 4 → 3 portions");
    await userEvent.click(lentils);
    expect(onSwapped).toHaveBeenCalledWith(swapped);
    const post = calls.find((c) => c.path.endsWith("/swap"));
    expect(post).toMatchObject({ method: "POST", path: "/api/v1/plans/5/meals/101/swap", body: { version_id: 7, allow_buying: false, offered_version_ids: [7, 8], exclude_version_ids: [2] } });
  });

  it("none fits: says so, and Write a new one asks for one ideas call", async () => {
    const calls = stubFetch([[result({ status: "none_fit", options: [], no_fit: "No other dinner fits Wednesday's calories and cook time." })], [result({ options: [option({ is_new: true, steps_ready: false, title: "Garlic chicken pilaf", version_id: 30 })], new_version_ids: [30] })]]);
    render(<SwapSheet planId={5} meal={dinner} away={[]} online onClose={() => undefined} onSwapped={() => undefined} />);
    expect(await screen.findByText("No other dinner fits Wednesday's calories and cook time.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Write a new one" }));
    const pilaf = await screen.findByRole("button", { name: "Swap to Garlic chicken pilaf" });
    expect(pilaf).toHaveTextContent("New");
    expect(pilaf).toHaveTextContent("Its steps are written when you first open it.");
    expect(calls.filter((c) => c.path.endsWith("/swap-options")).map((c) => (c.body as { allow_llm: boolean }).allow_llm)).toEqual([false, true]);
  });

  it("after Done shopping: options use what you have, and Allow buying asks again", async () => {
    const calls = stubFetch([[result({ after_shopping: true, options: [option()] })], [result({ after_shopping: true, options: [option({ buys: ["chickpeas ($1.29)"], cost_delta_cents: 129, cost_delta_display: "+$1.29 groceries" })] })]]);
    render(<SwapSheet planId={5} meal={dinner} away={[]} online onClose={() => undefined} onSwapped={() => undefined} />);
    expect(await screen.findByText("You've done the shopping, so these use what you have.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Allow buying" }));
    expect(await screen.findByText("Buys: chickpeas ($1.29)")).toBeInTheDocument();
    expect((calls[1]?.body as { allow_buying: boolean }).allow_buying).toBe(true);
  });

  it("a wait too long counts down, then tries again by itself", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = stubFetch([[result({ status: "waiting", options: [], retry_after_s: 2 })], [result()]]);
    render(<SwapSheet planId={5} meal={dinner} away={[]} online onClose={() => undefined} onSwapped={() => undefined} />);
    expect(await screen.findByText(/Trying again in 0:0/)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(await screen.findByText("Lentil stew")).toBeInTheDocument();
    expect(calls.filter((c) => c.path.endsWith("/swap-options"))).toHaveLength(2);
  });

  it("offline: nothing can be tapped", async () => {
    stubFetch([[result()]]);
    render(<SwapSheet planId={5} meal={dinner} away={[]} online={false} onClose={() => undefined} onSwapped={() => undefined} />);
    expect(await screen.findByRole("button", { name: "Swap to Lentil stew" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Write a new one" })).toBeDisabled();
  });
});

describe("Swap in the plan view", () => {
  const swapProps = (overrides: Partial<SwapProps> = {}): SwapProps => ({ away: {}, highlight: null, onSwapped: () => undefined, ...overrides });
  const twoDays = plan({
    id: 5,
    kind: "meal_prep",
    status: "draft",
    batches: [batch()],
    days: [
      day({ day: "2026-10-13", meals: [meal({ eat_on: "2026-10-13", slot: "dinner", plan_meal_id: 100, title: "Yesterday's chicken" })] }),
      day({ day: "2026-10-14", meals: [meal({ eat_on: "2026-10-14", slot: "dinner", plan_meal_id: 101 }), meal({ eat_on: "2026-10-14", slot: "lunch", plan_meal_id: 102, kind: "assembly", cook_batch_id: null, title: "Curry with rice" })] }),
    ],
  });

  it("⇄ Swap on each dish meal from today on; past days and assembled meals have none", async () => {
    render(<PlanView plan={twoDays} online today="2026-10-14" onAccepted={() => undefined} swap={swapProps()} />);
    const today = screen.getByRole("region", { name: "Today · Wed 14" });
    expect(within(today).getByRole("button", { name: "Swap Chicken over rice" })).toBeInTheDocument();
    expect(within(today).queryByRole("button", { name: "Swap Curry with rice" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Swap Yesterday's chicken" })).toBeNull();
  });

  it("the swapped-in meal is highlighted; the toast says what changed, with Undo", async () => {
    const onUndo = vi.fn();
    const { container } = render(
      <>
        <SwapToast message="Swapped. Also changed: Mon 12's Chicken over rice: 4 → 3 portions." undoing={false} error={null} onUndo={onUndo} onDismiss={() => undefined} />
        <PlanView plan={twoDays} online today="2026-10-14" onAccepted={() => undefined} swap={swapProps({ highlight: 101 })} />
      </>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Swapped. Also changed: Mon 12's Chicken over rice: 4 → 3 portions.");
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(onUndo).toHaveBeenCalledTimes(1);
    expect(container.querySelectorAll("li[class*='swapped']")).toHaveLength(1);
  });

  it("the meal row's ⋯ sheet opens the same Swap sheet", async () => {
    stubFetch([[result()]]);
    render(<PlanView plan={twoDays} online today="2026-10-14" onAccepted={() => undefined} swap={swapProps()} />);
    await userEvent.click(screen.getByRole("button", { name: "More for Chicken over rice" }));
    await userEvent.click(screen.getByRole("button", { name: "⇄ Swap this meal" }));
    expect(await screen.findByRole("dialog", { name: "Swap Wed 14 dinner" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Swap to Lentil stew" })).toBeInTheDocument();
  });

  it("a plan that isn't yours to change (superseded) shows no Swap", () => {
    render(<PlanView plan={{ ...twoDays, status: "superseded" }} online today="2026-10-14" onAccepted={() => undefined} swap={swapProps()} />);
    expect(screen.queryByRole("button", { name: /^Swap / })).toBeNull();
  });
});
