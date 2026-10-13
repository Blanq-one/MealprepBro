import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CookAnswers, PlanStreamEvent } from "@/lib/api/types";
import { prepFixes, startLabel, withMinutes, withStart } from "@/lib/cook/prep";
import { userSettings } from "@/test/fixtures";

import { NoPlanFits } from "./NoPlanFits";

const short = "Your inventory doesn't cover this week. The smallest top-up that makes a plan is about $36.20.";

function result(diagnostics: object[], detail = ""): PlanStreamEvent {
  return {
    event: "result",
    run_id: 3,
    elapsed_s: 4,
    status: "infeasible",
    notes: [],
    problem: { type: "about:blank", status: 422, title: "No plan fits this week", detail, diagnostics },
  } as unknown as PlanStreamEvent;
}

const answers: CookAnswers = {
  schema_version: 1,
  mode: "prep",
  goals: [],
  pantry: [],
  extras: [],
  allow_llm: true,
  shopping: "use_what_i_have",
  budget_cents: null,
  prep: { shape: "days", day_count: 3, slots: ["lunch", "dinner"], start: "2026-10-12", extra_to_freeze: 0, cook_style: "mix", cook_day: "today", sessions: [] },
};
const TODAY = new Date(2026, 9, 12); // Mon Oct 12

describe("no plan fits (M17, P4; C6 Infeasible)", () => {
  it("says each reason once, in plain words, with buttons for the fix and the items behind a tap", async () => {
    const onTopUp = vi.fn();
    const onShop = vi.fn();
    const event = result(
      [
        { code: "INVENTORY_SHORT", message: short, amount: 3620, suggested_cents: 3700, items: ["chicken thigh about 2 lb ($8.98)", "rice about 5 lb ($4.99)"] },
        { code: "INVENTORY_SHORT", message: short, amount: 3620, suggested_cents: 3700 },
      ],
      short, // the same words as the diagnostic: shown once
    );
    render(<NoPlanFits event={event} actions={{ onTopUp, onShop }} />);
    expect(screen.getAllByText(short)).toHaveLength(1);
    expect(screen.queryByText(/--topup|--budget/)).toBeNull(); // never command-line wording
    await userEvent.click(screen.getByRole("button", { name: "Allow a $37 top-up" }));
    expect(onTopUp).toHaveBeenCalledWith(3700);
    await userEvent.click(screen.getByRole("button", { name: "Switch to shopping" }));
    expect(onShop).toHaveBeenCalled();
    expect(screen.getByText("chicken thigh about 2 lb ($8.98)")).not.toBeVisible();
    await userEvent.click(screen.getByText("See what it would buy"));
    expect(screen.getByText("chicken thigh about 2 lb ($8.98)")).toBeVisible();
  });

  it("time and mood: each problem once, a button for each fix", async () => {
    const time = "Monday needs about 1 h 5 min start to finish; you set 1 h.";
    const mood = "6 recipes are fancy and your cook days are set to medium.";
    const onMinutes = vi.fn();
    const onMood = vi.fn();
    const event = result([
      { code: "COOK_TIME_SHORT", message: time, day: "2026-10-12", amount: 5, suggested_minutes: 65 },
      { code: "RECIPES_LEFT_OUT", message: mood, amount: 6, mood: "fancy" },
      { code: "COOK_TIME_SHORT", message: time, day: "2026-10-12", amount: 5, suggested_minutes: 65 },
    ]);
    render(<NoPlanFits event={event} actions={{ onMinutes, onMood }} />);
    expect(screen.getAllByText(time)).toHaveLength(1);
    expect(screen.getAllByText(mood)).toHaveLength(1);
    expect(screen.queryByText(/;\s*\./)).toBeNull(); // no stray punctuation
    await userEvent.click(screen.getByRole("button", { name: "Allow 65 min on Monday" }));
    expect(onMinutes).toHaveBeenCalledWith("2026-10-12", 65);
    await userEvent.click(screen.getByRole("button", { name: "Use simpler recipes" }));
    expect(onMood).toHaveBeenCalledWith("2026-10-12", "simple");
    await userEvent.click(screen.getByRole("button", { name: "Allow fancy recipes" }));
    expect(onMood).toHaveBeenCalledWith(null, "fancy");
  });

  it("a meal before the first cook day (AD3): Start on that cook day, or cook that day too", async () => {
    const onStart = vi.fn();
    const onMinutes = vi.fn();
    const message = "Fri 16's dinner comes before your first cook day (Sat 17), so nothing can be cooked for it.";
    render(<NoPlanFits event={result([{ code: "MEAL_BEFORE_COOK_DAY", message, day: "2026-10-16", suggested_minutes: 90, start_day: "2026-10-17" }])} actions={{ onStart, onMinutes }} />);
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Write new recipes" })).not.toBeInTheDocument(); // recipes can't help
    await userEvent.click(screen.getByRole("button", { name: /^Start (tomorrow|on Saturday)$/ }));
    expect(onStart).toHaveBeenCalledWith("2026-10-17");
    await userEvent.click(screen.getByRole("button", { name: "Cook on Friday too" }));
    expect(onMinutes).toHaveBeenCalledWith("2026-10-16", 90);
  });

  it("a budget shortfall offers the server's whole-dollar budget; settings fixes are links, each once", () => {
    const event = result([
      { code: "BUDGET_SHORT", message: "The cheapest plan that fits costs about $52.60 in regular groceries, $7.60 over your budget of $45.00.", suggested_cents: 5300 },
      { code: "KCAL_DAY_BELOW_FLOOR", message: "Mon Oct 12 can only reach about 1,500 kcal; the minimum is 1,650.", day: "2026-10-12" },
      { code: "KCAL_DAY_BELOW_FLOOR", message: "Tue Oct 13 can only reach about 1,520 kcal; the minimum is 1,650.", day: "2026-10-13" },
      { code: "HELD_INGREDIENTS", message: "These held items keep recipes out of the plan until you review them: gelatin" },
    ]);
    render(<NoPlanFits event={event} actions={{ onBudget: vi.fn() }} />);
    expect(screen.getByRole("button", { name: "Raise the budget to $53" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Change calories" })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Change calories" })).toHaveAttribute("href", expect.stringMatching(/field=meal_calories/));
    // one to three reasons shown; the rest behind a tap
    expect(screen.getByText("More reasons")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review held items", hidden: true })).toHaveAttribute("href", expect.stringMatching(/field=held_items/));
  });
});

describe("the fixes change only these answers", () => {
  const settings = userSettings();

  it("Start tomorrow (AD2, AD3): the plan moves to that day; sessions outside it and a cook day before it move too", () => {
    expect(startLabel("2026-10-13", TODAY)).toBe("Start tomorrow");
    expect(startLabel("2026-10-15", TODAY)).toBe("Start on Thursday");
    const moved = withStart(answers, "2026-10-13", TODAY);
    expect(moved.prep).toMatchObject({ start: "tomorrow", day_count: 3, cook_style: "mix" });
    const sessions = { ...answers, prep: { ...answers.prep!, cook_style: "sessions" as const, sessions: [{ day: "2026-10-12", minutes: 60 }, { day: "2026-10-14", minutes: 90 }, { day: "2026-10-16", minutes: 90 }] } };
    expect(withStart(sessions, "2026-10-14", TODAY).prep?.sessions).toEqual([{ day: "2026-10-14", minutes: 90 }, { day: "2026-10-16", minutes: 90 }]); // Wed 14 – Fri 16: Monday's left out
    const big = { ...answers, prep: { ...answers.prep!, cook_style: "big_day" as const, cook_day: "today" } };
    expect(withStart(big, "2026-10-14", TODAY).prep).toMatchObject({ start: "2026-10-14", cook_day: "2026-10-14" });
  });

  it("a top-up, a shopping list and a budget", () => {
    const rerun = vi.fn();
    const fixes = prepFixes({ ...answers, shopping: "make_a_list", budget_cents: 4500 }, settings, rerun);
    fixes.onTopUp(3700);
    expect(rerun).toHaveBeenLastCalledWith(expect.objectContaining({ shopping: "use_what_i_have", budget_cents: 3700 }));
    fixes.onShop();
    expect(rerun).toHaveBeenLastCalledWith(expect.objectContaining({ shopping: "make_a_list", budget_cents: null }));
    fixes.onBudget(5300);
    expect(rerun).toHaveBeenLastCalledWith(expect.objectContaining({ shopping: "make_a_list", budget_cents: 5300 }));
    fixes.onMood(null, "fancy");
    expect(rerun).toHaveBeenLastCalledWith(expect.objectContaining({ mood: "fancy" }));
  });

  it("Allow 65 min on Monday: mix it up becomes your cook days as sessions, with that day raised", () => {
    const out = withMinutes(answers, "2026-10-12", 105, settings, TODAY);
    // Mon and Wed are cook days in the default settings (90 min); Tue isn't
    expect(out.prep?.cook_style).toBe("sessions");
    expect(out.prep?.sessions).toEqual([
      { day: "2026-10-12", minutes: 105 },
      { day: "2026-10-14", minutes: 90 },
    ]);
  });

  it("on one big cook day the day's minutes go up; Quick is raised when it would cap them", () => {
    const big = { ...answers, goals: ["quick" as const], time_limit_minutes: 60, prep: { ...answers.prep!, cook_style: "big_day" as const, cook_minutes: 240 } };
    const out = withMinutes(big, "2026-10-12", 300, settings, TODAY);
    expect(out.prep?.cook_minutes).toBe(300);
    expect(out.time_limit_minutes).toBe(300);
    // no day: every cook day gets at least the minutes
    const every = withMinutes(answers, null, 120, settings, TODAY);
    expect(every.prep?.sessions?.every((s) => s.minutes >= 120)).toBe(true);
  });
});
