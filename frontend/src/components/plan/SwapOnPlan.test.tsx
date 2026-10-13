// Swap from the plan screen (step 2b.6 approval, A): a tapped option replaces the meal on a draft plan and on
// your current (accepted) plan, and a swap the server refuses says why and keeps the sheet open, never
// quietly showing the old meal again.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CookPlanPage from "@/app/cook/plan/page";
import type { PlanSummary, SwapOption, SwapResult, SwapStreamEvent } from "@/lib/api/types";
import { batch, day, meal, plan } from "@/test/fixtures";

const replace = vi.fn();
let search = new URLSearchParams("id=5");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => search,
}));

// days far ahead, so every meal is "from today on" whatever the date
const DAY = "2030-10-16";

function option(overrides: Partial<SwapOption> = {}): SwapOption {
  return {
    version_id: 7,
    recipe_id: 7,
    title: "Lentil stew",
    dish_category: "soup",
    kcal: 540,
    protein_g: "31.0",
    numbers: ["540 kcal", "31.0 g protein"],
    cost_delta_cents: 0,
    cost_delta_display: "No extra groceries",
    source_display: "Cook it that day",
    also_changed: [],
    buys: [],
    is_new: false,
    steps_ready: true,
    is_draft: true,
    fit: "exact",
    changes: [],
    ...overrides,
  };
}

function planWith(id: number, status: PlanSummary["status"], title: string, versionId: number): PlanSummary {
  return plan({
    id,
    kind: "meal_prep",
    status,
    batches: [batch({ id: 11, recipe_version_id: versionId, title, cook_on: DAY })],
    days: [day({ day: DAY, meals: [meal({ eat_on: DAY, slot: "dinner", plan_meal_id: 101 + id, recipe_version_id: versionId, title })] })],
  });
}

type Call = { method: string; path: string; body: unknown };

/** The API: the plan, the options stream for its meal, and the swap's answer (a SwapResult or a problem). */
function stubApi(current: PlanSummary, options: SwapOption[], swap: { status: number; body: unknown }): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ method: (init.method ?? "GET").toUpperCase(), path: url, body: typeof init.body === "string" ? JSON.parse(init.body) : undefined });
      const json = (body: unknown, status = 200, type = "application/json") => new Response(JSON.stringify(body), { status, headers: { "content-type": type } });
      if (url === `/api/v1/plans/${current.id}`) return json(current);
      if (url.endsWith("/swap-options")) {
        const result = { event: "result", plan_id: current.id, meal_id: 101 + current.id, elapsed_s: 1, status: "succeeded", options, can_write_new: false, after_shopping: false, notes: [], new_version_ids: [] } as SwapStreamEvent;
        const text = [{ event: "started", plan_id: current.id, meal_id: 101 + current.id, elapsed_s: 0 }, result].map((l) => JSON.stringify(l)).join("\n");
        return new Response(text, { status: 200, headers: { "content-type": "application/x-ndjson" } });
      }
      if (url.endsWith("/swap")) return json(swap.body, swap.status, swap.status === 200 ? "application/json" : "application/problem+json");
      return json({ title: "Not found", detail: url }, 404, "application/problem+json");
    }),
  );
  return calls;
}

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams("id=5");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function swapTo(title: string) {
  await userEvent.click(await screen.findByRole("button", { name: "Swap Chicken over rice" }));
  await userEvent.click(await screen.findByRole("button", { name: `Swap to ${title}` }));
}

describe.each(["draft", "active"] as const)("a swap on a %s plan", (status) => {
  it("shows the new meal, the toast with Undo, and follows the new version", async () => {
    const before = planWith(5, status, "Chicken over rice", 3);
    const after = planWith(6, status, "Lentil stew", 7);
    const swapped: SwapResult = { plan_id: 6, undo_plan_id: 5, plan_meal_id: 107, message: "Swapped.", also_changed: [], plan: after };
    const calls = stubApi(before, [option()], { status: 200, body: swapped });
    render(<CookPlanPage />);
    await swapTo("Lentil stew");
    const today = await screen.findByRole("region", { name: "Wed Oct 16" });
    expect(within(today).getByText("Lentil stew")).toBeInTheDocument();
    expect(within(today).queryByText("Chicken over rice")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("Swapped.");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(replace).toHaveBeenCalledWith("/cook/plan/?id=6");
    expect(calls.find((c) => c.path.endsWith("/swap"))?.body).toMatchObject({ version_id: 7, close: false });
  });
});

describe("a swap that can't be applied", () => {
  it("says why at the top of the sheet and on the option, keeps the sheet open and the meal as it was", async () => {
    const before = planWith(5, "draft", "Chicken over rice", 3);
    const problem = { type: "about:blank", title: "Conflict", status: 409, detail: "That recipe doesn't fit this meal any more. Pick another one." };
    stubApi(before, [option()], { status: 409, body: problem });
    render(<CookPlanPage />);
    await swapTo("Lentil stew");
    const sheet = await screen.findByRole("dialog", { name: /Swap/ });
    const alert = within(sheet).getByRole("alert");
    expect(alert).toHaveTextContent("Couldn't swap to Lentil stew: That recipe doesn't fit this meal any more. Pick another one.");
    expect(within(sheet).getByRole("button", { name: "Swap to Lentil stew" })).toHaveTextContent("Couldn't swap to Lentil stew");
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getAllByText("Chicken over rice").length).toBeGreaterThan(0);
  });

  it("a close fit says what it changes and is applied as a close fit", async () => {
    const before = planWith(5, "active", "Chicken over rice", 3);
    const close = option({ fit: "close", changes: ["+80 kcal over Wednesday's calories", "+10 min cook time on Wednesday"] });
    const after = planWith(6, "active", "Lentil stew", 7);
    const swapped: SwapResult = { plan_id: 6, undo_plan_id: 5, plan_meal_id: 107, message: "Swapped.", also_changed: [], plan: after };
    const calls = stubApi(before, [close], { status: 200, body: swapped });
    render(<CookPlanPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Swap Chicken over rice" }));
    expect(await screen.findByRole("heading", { name: "Nothing fits exactly. The closest:" })).toBeInTheDocument();
    const card = screen.getByRole("button", { name: "Swap to Lentil stew" });
    expect(card).toHaveTextContent("+80 kcal over Wednesday's calories");
    expect(card).toHaveTextContent("+10 min cook time on Wednesday");
    await userEvent.click(card);
    expect(calls.find((c) => c.path.endsWith("/swap"))?.body).toMatchObject({ version_id: 7, close: true });
  });
});
